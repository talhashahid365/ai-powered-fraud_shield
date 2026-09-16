import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../services/api";
import RiskBadge from "../components/RiskBadge";
import StatCard from "../components/StatCard";
import FraudNetworkGraph, { FraudNetworkLegend } from "../components/FraudNetworkGraph";
import type { FraudNetworkGraphData, FraudRing } from "../types";

function RingsTable({ rings, onSelect }: { rings: FraudRing[]; onSelect: (ringId: string) => void }) {
  if (rings.length === 0) {
    return (
      <p className="text-sm text-slate-400 py-6 text-center dark:text-slate-500">
        No fraud rings detected — no two customers currently share a device or IP address.
      </p>
    );
  }

  return (
    <table className="w-full text-sm">
      <thead className="bg-slate-50 text-slate-500 text-left dark:bg-white/5 dark:text-slate-400">
        <tr>
          <th className="px-4 py-2">Ring</th>
          <th className="px-4 py-2">Customers</th>
          <th className="px-4 py-2">Shared Devices</th>
          <th className="px-4 py-2">Shared IPs</th>
          <th className="px-4 py-2">Suspicious Txns</th>
          <th className="px-4 py-2">Avg Risk Score</th>
          <th className="px-4 py-2">Max Risk</th>
          <th className="px-4 py-2"></th>
        </tr>
      </thead>
      <tbody className="divide-y divide-slate-100 dark:divide-white/5">
        {rings.map((ring) => (
          <tr key={ring.ring_id} className="hover:bg-slate-50 dark:hover:bg-white/5">
            <td className="px-4 py-2 font-medium text-slate-700 dark:text-slate-200">{ring.size} customers</td>
            <td className="px-4 py-2">
              <div className="flex flex-wrap gap-1 max-w-md">
                {ring.customer_ids.slice(0, 6).map((cid) => (
                  <Link key={cid} to={`/customers/${cid}`} className="text-primary-600 hover:underline text-xs">
                    {cid}
                  </Link>
                ))}
                {ring.customer_ids.length > 6 && (
                  <span className="text-xs text-slate-400 dark:text-slate-500">+{ring.customer_ids.length - 6} more</span>
                )}
              </div>
            </td>
            <td className="px-4 py-2">{ring.shared_device_count}</td>
            <td className="px-4 py-2">{ring.shared_ip_count}</td>
            <td className="px-4 py-2 text-amber-600 dark:text-amber-400">{ring.total_suspicious_transactions}</td>
            <td className="px-4 py-2">{ring.avg_risk_score.toFixed(0)}</td>
            <td className="px-4 py-2"><RiskBadge level={ring.max_risk_level} /></td>
            <td className="px-4 py-2">
              <button onClick={() => onSelect(ring.ring_id)} className="text-primary-600 hover:underline text-xs font-medium">
                View graph →
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function FraudNetworkPage() {
  const { customerId } = useParams();
  const navigate = useNavigate();

  const [rings, setRings] = useState<FraudRing[] | null>(null);
  const [graph, setGraph] = useState<FraudNetworkGraphData | null>(null);
  const [graphLoading, setGraphLoading] = useState(false);
  const [graphError, setGraphError] = useState<string | null>(null);

  useEffect(() => {
    api.get("/fraud-network/rings").then((r) => setRings(r.data.rings));
  }, []);

  useEffect(() => {
    if (!customerId) {
      setGraph(null);
      return;
    }
    setGraphLoading(true);
    setGraphError(null);
    api
      .get(`/fraud-network/graph/${customerId}`)
      .then((r) => setGraph(r.data))
      .catch(() => setGraphError(`Could not load a network for ${customerId}.`))
      .finally(() => setGraphLoading(false));
  }, [customerId]);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Fraud Network Detection</h1>
        {customerId && (
          <button onClick={() => navigate("/fraud-network")} className="text-sm text-primary-600 hover:underline">
            ← Back to all rings
          </button>
        )}
      </div>

      {!customerId && (
        <>
          <p className="text-sm text-slate-500 mb-4 dark:text-slate-400">
            Groups of customers connected through a shared device or IP address — directly, or through a chain of
            other customers — ranked by risk. Click a ring to see the full Customer → Device → IP → Transaction →
            Location graph.
          </p>
          <div className="bg-white rounded-xl shadow-card border border-primary-100/70 overflow-hidden mb-8 dark:bg-[#141a2e] dark:border-white/10 dark:shadow-none">
            {rings === null ? (
              <p className="text-slate-400 p-6 dark:text-slate-500">Loading...</p>
            ) : (
              <RingsTable rings={rings} onSelect={(ringId) => navigate(`/fraud-network/${ringId}`)} />
            )}
          </div>
        </>
      )}

      {customerId && (
        <div>
          {graphLoading && <p className="text-slate-400 dark:text-slate-500">Loading network...</p>}
          {graphError && <p className="text-red-600 text-sm dark:text-red-400">{graphError}</p>}
          {graph && (
            <>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                <StatCard label="Customers in Ring" value={graph.customer_count ?? graph.nodes.filter((n) => n.type === "customer").length} />
                <StatCard label="Shared Devices" value={graph.shared_device_count ?? 0} />
                <StatCard label="Shared IPs" value={graph.shared_ip_count ?? 0} />
                <StatCard label="Linking Transactions" value={graph.linking_transaction_count ?? 0} />
              </div>
              {graph.truncated && (
                <p className="text-xs text-amber-600 mb-3 dark:text-amber-400">
                  This ring is large — the graph below has been truncated to keep it readable.
                </p>
              )}
              <div className="bg-white rounded-xl shadow-card border border-primary-100/70 p-4 dark:bg-[#141a2e] dark:border-white/10 dark:shadow-none">
                <FraudNetworkLegend />
                {graph.nodes.filter((n) => n.type === "customer").length > 1 ? (
                  <FraudNetworkGraph
                    nodes={graph.nodes}
                    edges={graph.edges}
                    height={520}
                    onNodeClick={(node) => {
                      if (node.type === "customer") navigate(`/customers/${node.label}`);
                    }}
                  />
                ) : (
                  <p className="text-sm text-slate-400 py-6 text-center dark:text-slate-500">
                    {customerId} has no shared devices or IP addresses with any other customer.
                  </p>
                )}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
