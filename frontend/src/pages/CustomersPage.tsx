import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../services/api";
import RiskBadge from "../components/RiskBadge";
import type { Customer } from "../types";

export default function CustomersPage() {
  const [customers, setCustomers] = useState<Customer[]>([]);

  useEffect(() => {
    api.get("/customers").then((r) => setCustomers(r.data));
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Customer Risk Profiles</h1>
      <div className="bg-white rounded-xl shadow-card border border-primary-100/70 overflow-hidden dark:bg-[#141a2e] dark:border-white/10 dark:shadow-none">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-500 text-left dark:bg-white/5 dark:text-slate-400">
            <tr>
              <th className="px-4 py-2">Customer</th>
              <th className="px-4 py-2">Risk</th>
              <th className="px-4 py-2">Total Txns</th>
              <th className="px-4 py-2">Suspicious</th>
              <th className="px-4 py-2">Devices</th>
              <th className="px-4 py-2">Locations</th>
              <th className="px-4 py-2">Fraud Reports</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-white/5">
            {customers.map((c) => (
              <tr key={c.id} className="hover:bg-slate-50 dark:hover:bg-white/5">
                <td className="px-4 py-2">
                  <Link to={`/customers/${c.customer_id}`} className="text-primary-600 hover:underline">{c.customer_id}</Link>
                </td>
                <td className="px-4 py-2"><RiskBadge level={c.risk_level} /></td>
                <td className="px-4 py-2">{c.total_transactions}</td>
                <td className="px-4 py-2">{c.suspicious_transactions}</td>
                <td className="px-4 py-2">{c.devices_used}</td>
                <td className="px-4 py-2">{c.locations_used}</td>
                <td className="px-4 py-2">{c.previous_fraud_reports}</td>
              </tr>
            ))}
            {customers.length === 0 && (
              <tr><td colSpan={7} className="px-4 py-6 text-center text-slate-400 dark:text-slate-500">No customers yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
