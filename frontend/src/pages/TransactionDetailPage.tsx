import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../services/api";
import RiskBadge from "../components/RiskBadge";
import type { Transaction } from "../types";

export default function TransactionDetailPage() {
  const { id } = useParams();
  const [txn, setTxn] = useState<Transaction | null>(null);
  const [explanation, setExplanation] = useState<string | null>(null);

  useEffect(() => {
    api.get(`/transactions/${id}`).then((r) => setTxn(r.data));
    api.get(`/transactions/${id}/risk`).then((r) => setExplanation(r.data.explanation));
  }, [id]);

  if (!txn) return <p className="text-slate-400 dark:text-slate-500">Loading...</p>;

  const rows: [string, string | number][] = [
    ["Transaction ID", txn.transaction_id],
    ["Customer", txn.customer_id],
    ["Amount", `${txn.currency} ${txn.amount.toLocaleString()}`],
    ["Payment Method", txn.payment_method ?? "—"],
    ["Device", txn.device_id ?? "—"],
    ["IP Address", txn.ip_address ?? "—"],
    ["Location", txn.location ?? "—"],
    ["Customer Account Age", `${txn.account_age_days} day${txn.account_age_days === 1 ? "" : "s"}`],
    ["Previous Transactions", txn.previous_transaction_count],
    ["Status", txn.transaction_status],
    ["Decision", txn.decision],
    ["Anomaly Score", txn.anomaly_score.toFixed(1)],
    ["Rule Score", txn.rule_score.toFixed(1)],
    ["Date", new Date(txn.transaction_datetime).toLocaleString()],
  ];

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <h1 className="text-2xl font-bold">Transaction {txn.transaction_id}</h1>
        <RiskBadge level={txn.risk_level} />
        <span className="text-slate-500 text-sm dark:text-slate-400">Risk Score: {txn.risk_score.toFixed(0)}/100</span>
        <Link
          to={`/customers/${txn.customer_id}`}
          className="ml-auto text-sm text-primary-600 hover:underline"
        >
          View full customer history &rarr;
        </Link>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl shadow-card border border-primary-100/70 p-4 dark:bg-[#141a2e] dark:border-white/10 dark:shadow-none">
          <h2 className="font-semibold mb-3">Details</h2>
          <dl className="text-sm divide-y divide-slate-100 dark:divide-white/5">
            {rows.map(([label, value]) => (
              <div key={label} className="flex justify-between py-1.5">
                <dt className="text-slate-500 dark:text-slate-400">{label}</dt>
                <dd className="font-medium">{value}</dd>
              </div>
            ))}
          </dl>
        </div>

        <div className="bg-white rounded-xl shadow-card border border-primary-100/70 p-4 dark:bg-[#141a2e] dark:border-white/10 dark:shadow-none">
          <h2 className="font-semibold mb-3">AI Explanation</h2>
          <pre className="whitespace-pre-wrap text-sm text-slate-700 font-sans dark:text-slate-300">{explanation || "No explanation generated (low risk)."}</pre>
        </div>
      </div>
    </div>
  );
}
