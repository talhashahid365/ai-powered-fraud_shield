import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../services/api";
import { useAuth } from "../hooks/useAuth";
import RiskBadge from "../components/RiskBadge";
import StatCard from "../components/StatCard";
import FraudNetworkGraph, { FraudNetworkLegend } from "../components/FraudNetworkGraph";
import AIInvestigationAssistant from "../components/AIInvestigationAssistant";
import type { Customer, NetworkEdge, NetworkNode } from "../types";

export default function CustomerProfilePage() {
  const { customerId } = useParams();
  const { user } = useAuth();
  const canInvestigate = user?.role === "ADMIN" || user?.role === "ANALYST";
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [transactions, setTransactions] = useState<any[]>([]);
  const [network, setNetwork] = useState<{ nodes: NetworkNode[]; edges: NetworkEdge[] } | null>(null);

  useEffect(() => {
    api.get(`/customers/${customerId}/transactions`).then((r) => {
      setCustomer(r.data.customer);
      setTransactions(r.data.transactions);
    });
    api.get(`/customers/${customerId}/network`).then((r) => setNetwork(r.data));
  }, [customerId]);

  if (!customer) return <p className="text-slate-400 dark:text-slate-500">Loading...</p>;

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <h1 className="text-2xl font-bold">Customer: {customer.customer_id}</h1>
        <RiskBadge level={customer.risk_level} />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-8">
        <StatCard label="Risk Score" value={customer.risk_score.toFixed(0)} />
        <StatCard label="Total Transactions" value={customer.total_transactions} />
        <StatCard label="Suspicious Transactions" value={customer.suspicious_transactions} accent="text-amber-600" />
        <StatCard label="Devices Used" value={customer.devices_used} />
        <StatCard label="Locations Used" value={customer.locations_used} />
        <StatCard label="Previous Fraud Reports" value={customer.previous_fraud_reports} accent="text-red-600" />
      </div>

      {canInvestigate && (
        <div className="mb-6">
          <AIInvestigationAssistant
            customerId={customer.customer_id}
            suggestedQuestions={[
              "Why is this customer suspicious?",
              "Show me unusual activity from this customer.",
              "How many devices and locations has this customer used?",
            ]}
          />
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl shadow-card border border-primary-100/70 p-4 dark:bg-[#141a2e] dark:border-white/10 dark:shadow-none">
          <h2 className="font-semibold mb-3">Transaction History</h2>
          <ul className="divide-y divide-slate-100 text-sm max-h-96 overflow-y-auto dark:divide-white/5">
            {transactions.map((t) => (
              <li key={t.id} className="py-2 flex justify-between">
                <span>{t.transaction_id} — ${t.amount.toLocaleString()}</span>
                <RiskBadge level={t.risk_level} />
              </li>
            ))}
            {transactions.length === 0 && <li className="py-2 text-slate-400 dark:text-slate-500">No transactions yet.</li>}
          </ul>
        </div>

        <div className="bg-white rounded-xl shadow-card border border-primary-100/70 p-4 dark:bg-[#141a2e] dark:border-white/10 dark:shadow-none">
          <div className="flex items-center justify-between mb-1">
            <h2 className="font-semibold">Fraud Network</h2>
            <Link to={`/fraud-network/${customer.customer_id}`} className="text-xs text-primary-600 hover:underline">
              Open full network view →
            </Link>
          </div>
          <FraudNetworkLegend />
          {network && network.nodes.length > 1 ? (
            <FraudNetworkGraph nodes={network.nodes} edges={network.edges} />
          ) : (
            <p className="text-sm text-slate-400 dark:text-slate-500">No shared devices or IP addresses detected.</p>
          )}
        </div>
      </div>
    </div>
  );
}
