"""
Generate realistic mock transaction data for development and ML training.

Produces a CSV with columns matching the backend's CSV import contract:
transaction_id, customer_id, amount, currency, transaction_datetime,
payment_method, ip_address, device_id, location

Includes: normal transactions, high-value transactions, rapid transactions,
new-device transactions, shared-IP transactions, suspicious locations, and
behavior anomalies -- per spec section 26.

Usage:
    python generate_mock_transactions.py --rows 5000 --out mock_transactions.csv
"""
import argparse
import csv
import random
from datetime import datetime, timedelta

PAYMENT_METHODS = ["credit_card", "debit_card", "paypal", "bank_transfer", "crypto"]
LOCATIONS = ["Islamabad", "Lahore", "Karachi", "Peshawar", "Dubai", "London", "New York"]


def make_customers(n=200):
    customers = []
    for i in range(n):
        customers.append({
            "customer_id": f"CUST-{1000 + i}",
            "avg_amount": random.uniform(20, 300),
            "home_location": random.choice(LOCATIONS),
            "devices": [f"DEV-{random.randint(1, 9999)}" for _ in range(random.randint(1, 2))],
            "ips": [f"192.168.{random.randint(0,255)}.{random.randint(0,255)}" for _ in range(random.randint(1, 2))],
        })
    return customers


def generate(rows: int):
    customers = make_customers()
    shared_device = "DEV-SHARED-001"
    shared_ip = "10.0.0.99"
    start_time = datetime(2026, 1, 1)

    transactions = []
    for i in range(rows):
        customer = random.choice(customers)
        txn_type = random.choices(
            ["normal", "high_value", "rapid", "new_device", "shared_ip", "suspicious_location"],
            weights=[60, 10, 10, 8, 6, 6],
        )[0]

        amount = round(random.gauss(customer["avg_amount"], customer["avg_amount"] * 0.2), 2)
        device_id = random.choice(customer["devices"])
        ip_address = random.choice(customer["ips"])
        location = customer["home_location"]
        dt = start_time + timedelta(minutes=random.randint(0, 60 * 24 * 90))

        if txn_type == "high_value":
            amount = customer["avg_amount"] * random.uniform(8, 25)
        elif txn_type == "new_device":
            device_id = f"DEV-NEW-{random.randint(10000, 99999)}"
            amount = customer["avg_amount"] * random.uniform(3, 10)
        elif txn_type == "shared_ip":
            ip_address = shared_ip
        elif txn_type == "suspicious_location":
            location = random.choice([l for l in LOCATIONS if l != customer["home_location"]])
        elif txn_type == "rapid":
            # emit a burst of 4-6 transactions within a few minutes
            burst_count = random.randint(4, 6)
            for b in range(burst_count):
                transactions.append({
                    "transaction_id": f"TXN-{100000 + len(transactions)}",
                    "customer_id": customer["customer_id"],
                    "amount": round(max(1, amount), 2),
                    "currency": "USD",
                    "transaction_datetime": (dt + timedelta(seconds=b * 60)).strftime("%Y-%m-%d %H:%M:%S"),
                    "payment_method": random.choice(PAYMENT_METHODS),
                    "ip_address": ip_address,
                    "device_id": device_id,
                    "location": location,
                })
            continue

        transactions.append({
            "transaction_id": f"TXN-{100000 + len(transactions)}",
            "customer_id": customer["customer_id"],
            "amount": round(max(1, amount), 2),
            "currency": "USD",
            "transaction_datetime": dt.strftime("%Y-%m-%d %H:%M:%S"),
            "payment_method": random.choice(PAYMENT_METHODS),
            "ip_address": ip_address,
            "device_id": device_id,
            "location": location,
        })

    return transactions


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=2000)
    parser.add_argument("--out", type=str, default="mock_transactions.csv")
    args = parser.parse_args()

    transactions = generate(args.rows)
    fieldnames = ["transaction_id", "customer_id", "amount", "currency", "transaction_datetime",
                  "payment_method", "ip_address", "device_id", "location"]

    with open(args.out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(transactions)

    print(f"Wrote {len(transactions)} mock transactions to {args.out}")


if __name__ == "__main__":
    main()
