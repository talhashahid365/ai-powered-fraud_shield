import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../services/api";
import RiskBadge from "../components/RiskBadge";
import type { Alert } from "../types";

const STATUS_OPTIONS = ["", "NEW", "INVESTIGATING", "CONFIRMED_FRAUD", "FALSE_POSITIVE", "RESOLVED"];

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [statusFilter, setStatusFilter] = useState("");

  useEffect(() => {
    api.get("/alerts", { params: { status_filter: statusFilter || undefined } }).then((r) => setAlerts(r.data));
  }, [statusFilter]);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Fraud Alerts</h1>
        <select className="border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/30 focus:border-primary-400 transition bg-white dark:bg-white/5 dark:border-white/10 dark:text-slate-100 dark:placeholder:text-slate-500" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          {STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>{s || "All Statuses"}</option>
          ))}
        </select>
      </div>

      <div className="grid gap-3">
        {alerts.map((a) => (
          <Link
            key={a.id}
            to={`/alerts/${a.id}`}
            className="bg-white border border-primary-100/70 rounded-xl p-4 flex items-center justify-between hover:shadow-sm dark:bg-[#141a2e] dark:border-white/10 dark:hover:shadow-none"
          >
            <div>
              <div className="font-medium">{a.title}</div>
              <div className="text-sm text-slate-500 dark:text-slate-400">{a.reason}</div>
            </div>
            <div className="flex items-center gap-3">
              <RiskBadge level={a.severity} />
              <span className="text-xs text-slate-500 dark:text-slate-400">{a.status}</span>
              <span className="text-xs text-slate-400 dark:text-slate-500">{a.assigned_to ? "Assigned" : "Unassigned"}</span>
            </div>
          </Link>
        ))}
        {alerts.length === 0 && <p className="text-slate-400 text-sm dark:text-slate-500">No alerts found.</p>}
      </div>
    </div>
  );
}
