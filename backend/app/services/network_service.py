"""
Fraud Network Detection.

Builds the Customer -> Device -> IP -> Transaction -> Location relationship
graph, and detects "fraud rings": groups of two or more customers connected
through a shared device or IP address - directly, or transitively through a
chain of other customers/devices/IPs. Example of what this is meant to
surface (from the feature spec):

    Customer A ── Device X ── IP 192.168.x.x
                                    │
    Customer B ─────────────────────┘
                                    │
    Customer C ── Device X

Customer A and Customer C never share an IP directly, and Customer B never
used Device X - but all three are one ring because they're chained together
through shared identifiers. A "who directly shares a device/IP with this
one customer" view only ever finds 1-hop neighbors and misses exactly this
kind of ring, so both the per-customer quick view (routes/customers.py
get_customer_network) AND this module exist: the former is a fast 1-hop
sanity check on a single customer's profile page, this module is the real
transitive detector used by the standalone Fraud Network page.
"""
from collections import defaultdict
from typing import Iterable

from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.transaction import Transaction

# Hard caps so one enormous, densely-connected component (e.g. everyone
# sharing a single misconfigured corporate NAT IP) can't make a single graph
# request scan or render an unbounded amount of data.
MAX_GRAPH_NODES = 300
MAX_GRAPH_DEPTH = 4

_RISK_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


def _expand_component(db: Session, seed_customer_ids: set[str], depth: int, max_nodes: int) -> tuple[set[str], bool]:
    """
    BFS outward from seed_customer_ids across shared device_id/ip_address
    links, up to `depth` hops or `max_nodes` customers - whichever comes
    first. Returns (customer_ids_in_component, truncated).
    """
    customer_ids = set(seed_customer_ids)
    frontier = set(seed_customer_ids)
    truncated = False

    for _ in range(depth):
        if not frontier or len(customer_ids) >= max_nodes:
            break

        txns = db.query(Transaction.device_id, Transaction.ip_address).filter(
            Transaction.customer_id.in_(frontier)
        ).all()
        device_ids = {d for d, _ in txns if d}
        ip_addresses = {ip for _, ip in txns if ip}

        next_ids: set[str] = set()
        if device_ids:
            rows = db.query(Transaction.customer_id).filter(Transaction.device_id.in_(device_ids)).distinct().all()
            next_ids.update(r[0] for r in rows)
        if ip_addresses:
            rows = db.query(Transaction.customer_id).filter(Transaction.ip_address.in_(ip_addresses)).distinct().all()
            next_ids.update(r[0] for r in rows)

        new_ids = next_ids - customer_ids
        if len(customer_ids) + len(new_ids) > max_nodes:
            truncated = True
            new_ids = set(list(new_ids)[: max(max_nodes - len(customer_ids), 0)])

        customer_ids.update(new_ids)
        frontier = new_ids

    return customer_ids, truncated


def build_customer_network(db: Session, root_customer: Customer, depth: int = 3, max_nodes: int = MAX_GRAPH_NODES) -> dict:
    """
    Full Customer -> Device -> IP -> Transaction -> Location graph for the
    entire fraud ring root_customer belongs to (not just its direct
    neighbors). Only transactions on a device/IP that is actually shared by
    2+ customers in the discovered component are drawn as evidence
    (Transaction/Location nodes) - this is what keeps the graph readable:
    an active customer's hundreds of routine, non-shared transactions never
    appear, only the ones that actually connect this ring together.
    """
    depth = max(1, min(depth, MAX_GRAPH_DEPTH))
    customer_ids, truncated = _expand_component(db, {root_customer.id}, depth, max_nodes)

    customers = db.query(Customer).filter(Customer.id.in_(customer_ids)).all()
    txns = db.query(Transaction).filter(Transaction.customer_id.in_(customer_ids)).all()

    graph = _assemble_graph(customers, txns)
    graph["root_customer_id"] = root_customer.customer_id
    graph["truncated"] = truncated
    return graph


def _assemble_graph(customers: Iterable[Customer], txns: Iterable[Transaction]) -> dict:
    customers_by_id = {c.id: c for c in customers}
    txns = list(txns)

    device_customers: dict[str, set[str]] = defaultdict(set)
    ip_customers: dict[str, set[str]] = defaultdict(set)
    for t in txns:
        if t.device_id:
            device_customers[t.device_id].add(t.customer_id)
        if t.ip_address:
            ip_customers[t.ip_address].add(t.customer_id)

    shared_devices = {d for d, custs in device_customers.items() if len(custs) >= 2}
    shared_ips = {ip for ip, custs in ip_customers.items() if len(custs) >= 2}

    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    def add_node(node: dict) -> None:
        nodes.setdefault(node["id"], node)

    for c in customers_by_id.values():
        add_node({"id": c.customer_id, "type": "customer", "label": c.customer_id, "risk_level": c.risk_level.value})

    linking_transaction_count = 0
    for t in sorted(txns, key=lambda t: t.transaction_datetime):
        cust = customers_by_id.get(t.customer_id)
        if not cust:
            continue

        is_linking_device = bool(t.device_id) and t.device_id in shared_devices
        is_linking_ip = bool(t.ip_address) and t.ip_address in shared_ips
        if not (is_linking_device or is_linking_ip):
            continue  # routine, non-shared transaction - not evidence of a connection

        linking_transaction_count += 1
        anchor = cust.customer_id

        if t.device_id:
            device_node_id = f"device:{t.device_id}"
            add_node({"id": device_node_id, "type": "device", "label": t.device_id})
            edges.append({"source": cust.customer_id, "target": device_node_id, "type": "used_device"})
            anchor = device_node_id

        if t.ip_address:
            ip_node_id = f"ip:{t.ip_address}"
            add_node({"id": ip_node_id, "type": "ip", "label": t.ip_address})
            edges.append({"source": anchor, "target": ip_node_id, "type": "from_ip"})
            anchor = ip_node_id

        txn_node_id = f"txn:{t.transaction_id}"
        add_node({
            "id": txn_node_id,
            "type": "transaction",
            "label": t.transaction_id,
            "risk_level": t.risk_level.value,
            "amount": t.amount,
        })
        edges.append({"source": anchor, "target": txn_node_id, "type": "transaction"})

        if t.location:
            location_node_id = f"location:{t.location}"
            add_node({"id": location_node_id, "type": "location", "label": t.location})
            edges.append({"source": txn_node_id, "target": location_node_id, "type": "occurred_at"})

    return {
        "nodes": list(nodes.values()),
        "edges": edges,
        "customer_count": len(customers_by_id),
        "shared_device_count": len(shared_devices),
        "shared_ip_count": len(shared_ips),
        "linking_transaction_count": linking_transaction_count,
    }


def detect_fraud_rings(db: Session, min_ring_size: int = 2, limit: int = 100) -> list[dict]:
    """
    Union-find over every transaction's (customer, device_id, ip_address):
    two customers are linked if they share a device or IP, directly or
    transitively through a chain of other customers. Every resulting
    connected component of size >= min_ring_size is a fraud ring candidate,
    ranked by risk level, then size, then average risk score.
    """
    rows = db.query(Transaction.customer_id, Transaction.device_id, Transaction.ip_address).all()

    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    device_customers: dict[str, set[str]] = defaultdict(set)
    ip_customers: dict[str, set[str]] = defaultdict(set)
    device_first_customer: dict[str, str] = {}
    ip_first_customer: dict[str, str] = {}

    for customer_id, device_id, ip_address in rows:
        find(customer_id)  # ensure every customer with a transaction is registered, even if never linked
        if device_id:
            device_customers[device_id].add(customer_id)
            if device_id in device_first_customer:
                union(customer_id, device_first_customer[device_id])
            else:
                device_first_customer[device_id] = customer_id
        if ip_address:
            ip_customers[ip_address].add(customer_id)
            if ip_address in ip_first_customer:
                union(customer_id, ip_first_customer[ip_address])
            else:
                ip_first_customer[ip_address] = customer_id

    components: dict[str, set[str]] = defaultdict(set)
    for customer_id in parent:
        components[find(customer_id)].add(customer_id)

    ring_member_sets = [members for members in components.values() if len(members) >= min_ring_size]
    if not ring_member_sets:
        return []

    customer_devices: dict[str, set[str]] = defaultdict(set)
    customer_ips: dict[str, set[str]] = defaultdict(set)
    for device_id, custs in device_customers.items():
        for cid in custs:
            customer_devices[cid].add(device_id)
    for ip_address, custs in ip_customers.items():
        for cid in custs:
            customer_ips[cid].add(ip_address)

    all_member_ids = {cid for members in ring_member_sets for cid in members}
    customers_by_id = {c.id: c for c in db.query(Customer).filter(Customer.id.in_(all_member_ids)).all()}

    rings: list[dict] = []
    for members in ring_member_sets:
        member_customers = [customers_by_id[m] for m in members if m in customers_by_id]
        if len(member_customers) < min_ring_size:
            continue

        shared_devices = {
            d for m in members for d in customer_devices.get(m, set()) if len(device_customers[d]) >= 2
        }
        shared_ips = {
            ip for m in members for ip in customer_ips.get(m, set()) if len(ip_customers[ip]) >= 2
        }
        total_suspicious = sum(c.suspicious_transactions for c in member_customers)
        avg_risk_score = sum(c.risk_score for c in member_customers) / len(member_customers)
        max_risk_level = max((c.risk_level.value for c in member_customers), key=lambda lvl: _RISK_ORDER.get(lvl, 0))
        # Deterministic id so the same ring always resolves to the same
        # graph endpoint, even across requests: the lowest customer_id in
        # the ring, which any member can be looked up by.
        sorted_customer_ids = sorted(c.customer_id for c in member_customers)

        rings.append({
            "ring_id": sorted_customer_ids[0],
            "size": len(member_customers),
            "customer_ids": sorted_customer_ids,
            "shared_device_count": len(shared_devices),
            "shared_ip_count": len(shared_ips),
            "total_suspicious_transactions": total_suspicious,
            "avg_risk_score": round(avg_risk_score, 1),
            "max_risk_level": max_risk_level,
        })

    rings.sort(
        key=lambda r: (_RISK_ORDER.get(r["max_risk_level"], 0), r["size"], r["avg_risk_score"]),
        reverse=True,
    )
    return rings[:limit]
