import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { api } from "../services/api";
import { useAuth } from "../hooks/useAuth";
import { useLiveFeed } from "../hooks/useLiveFeed";
import { useTheme } from "../hooks/useTheme";
import StatCard from "../components/StatCard";
import RiskBadge from "../components/RiskBadge";
import type { DashboardSummary } from "../types";

interface TrendPoint {
  date: string;
  suspicious_transactions: number;
}

interface RecentAlert {
  id: string;
  title: string;
  severity: string;
  status: string;
  created_at: string;
}

interface RecentTransaction {
  id: string;
  transaction_id: string;
  amount: number;
  currency: string;
  risk_level: string;
  decision: string;
  created_at: string;
}

export default function DashboardPage() {
  const { user } = useAuth();
  const { theme } = useTheme();
  const axisColor = theme === "dark" ? "#94a3b8" : "#64748b";
  const gridColor = theme === "dark" ? "rgba(255,255,255,0.08)" : "#eef2f7";
  const tooltipStyle =
    theme === "dark"
      ? { background: "#1a2140", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 12, color: "#e2e4f3" }
      : { background: "#fff", border: "1px solid #f1f0fb", borderRadius: 12, color: "#1e1b3a" };
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [trend, setTrend] = useState<TrendPoint[]>([]);
  const [recentAlerts, setRecentAlerts] = useState<RecentAlert[]>([]);
  const [openAlerts, setOpenAlerts] = useState<RecentAlert[]>([]);
  const [recentTransactions, setRecentTransactions] = useState<RecentTransaction[]>([]);
  const [liveCount, setLiveCount] = useState(0);

  const isAnalyst = user?.role === "ANALYST";
  const isManager = user?.role === "BUSINESS_MANAGER";

  function refreshRoleFeed() {
    if (isAnalyst) {
      api.get("/alerts", { params: { status_filter: "NEW" } }).then((r) => setOpenAlerts(r.data));
    } else if (isManager) {
      api.get("/dashboard/recent-transactions", { params: { limit: 10 } }).then((r) => setRecentTransactions(r.data));
    } else {
      api.get("/dashboard/recent-alerts").then((r) => setRecentAlerts(r.data));
    }
  }

  useEffect(() => {
    api.get("/dashboard/summary").then((r) => setSummary(r.data));
    api.get("/dashboard/fraud-trend").then((r) => setTrend(r.data));
    refreshRoleFeed();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAnalyst, isManager]);

  // Live push from the detection pipeline (see backend app/api/routes/ws.py): every
  // scored transaction arrives here the moment it's decided, instead of only appearing
  // after a manual refresh. Refresh only the role-relevant feed + bump the running
  // stat counters locally, rather than a heavy full-page refetch per event.
  useLiveFeed((event) => {
    const t = event.transaction;
    setLiveCount((c) => c + 1);
    setSummary((prev) =>
      prev
        ? {
            ...prev,
            total_transactions: prev.total_transactions + 1,
            high_risk_transactions: prev.high_risk_transactions + (t.risk_level === "HIGH" ? 1 : 0),
            medium_risk_transactions: prev.medium_risk_transactions + (t.risk_level === "MEDIUM" ? 1 : 0),
          }
        : prev
    );
    if (t.risk_level !== "LOW" || isManager) {
      refreshRoleFeed();
    }
  });

  const heading = isAnalyst ? "My Investigation Queue" : isManager ? "Business Overview" : "Dashboard";
  const subheading = isAnalyst
    ? "Alerts waiting for review, plus a quick view of overall system risk."
    : isManager
    ? "Transactions you've submitted or imported, and how they were scored."
    : "System-wide transaction and fraud overview.";

  return (
    <div>
      <div className="flex items-center gap-2 mb-1">
        <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-50">{heading}</h1>
        <span className="flex items-center gap-1.5 text-xs font-medium text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/20 rounded-full px-2 py-0.5">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          Live{liveCount > 0 ? ` · ${liveCount} new` : ""}
        </span>
      </div>
      <p className="text-sm text-slate-500 dark:text-slate-400 mb-6">{subheading}</p>

      {isAnalyst && (
        <div className="app-card mb-8">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold text-slate-800 dark:text-slate-100">Alerts Needing Investigation ({openAlerts.length})</h2>
            <Link to="/alerts" className="text-sm text-primary-600 dark:text-primary-400 hover:underline">View all alerts →</Link>
          </div>
          <ul className="divide-y divide-slate-100 dark:divide-white/5">
            {openAlerts.slice(0, 8).map((a) => (
              <li key={a.id}>
                <Link to={`/alerts/${a.id}`} className="py-2 flex items-center justify-between text-sm hover:bg-slate-50 dark:hover:bg-white/5 -mx-4 px-4 text-slate-700 dark:text-slate-200">
                  <span>{a.title}</span>
                  <RiskBadge level={a.severity} />
                </Link>
              </li>
            ))}
            {openAlerts.length === 0 && <li className="py-2 text-sm text-slate-400 dark:text-slate-500">Nothing new — queue is clear. 🎉</li>}
          </ul>
        </div>
      )}

      {isManager && (
        <div className="app-card mb-8">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold text-slate-800 dark:text-slate-100">Recently Added Transactions</h2>
            <Link to="/transactions" className="text-sm text-primary-600 dark:text-primary-400 hover:underline">
              Add / import a transaction →
            </Link>
          </div>
          <ul className="divide-y divide-slate-100 dark:divide-white/5">
            {recentTransactions.map((t) => (
              <li key={t.id}>
                <Link
                  to={`/transactions/${t.id}`}
                  className="py-2 flex items-center justify-between text-sm hover:bg-slate-50 dark:hover:bg-white/5 -mx-4 px-4 text-slate-700 dark:text-slate-200"
                >
                  <span>
                    {t.transaction_id} — {t.currency} {t.amount.toLocaleString()}
                  </span>
                  <span className="flex items-center gap-2">
                    <RiskBadge level={t.risk_level} />
                    <span className="text-xs text-slate-500 dark:text-slate-400">{t.decision}</span>
                  </span>
                </Link>
              </li>
            ))}
            {recentTransactions.length === 0 && (
              <li className="py-2 text-sm text-slate-400 dark:text-slate-500">No transactions added yet — import a CSV or add one manually.</li>
            )}
          </ul>
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <StatCard label="Total Transactions" value={summary?.total_transactions ?? "—"} />
        <StatCard label="High Risk" value={summary?.high_risk_transactions ?? "—"} accent="text-red-600" />
        <StatCard label="Medium Risk" value={summary?.medium_risk_transactions ?? "—"} accent="text-amber-600" />
        {!isManager && <StatCard label="Fraud Alerts" value={summary?.fraud_alerts ?? "—"} />}
        {!isManager && <StatCard label="Confirmed Fraud" value={summary?.confirmed_fraud ?? "—"} accent="text-red-700" />}
        {!isManager && <StatCard label="False Positives" value={summary?.false_positives ?? "—"} />}
        <StatCard label="Avg. Risk Score" value={summary?.average_risk_score ?? "—"} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="app-card">
          <h2 className="font-semibold mb-3 text-slate-800 dark:text-slate-100">Fraud Trend (suspicious transactions)</h2>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={trend}>
              <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
              <XAxis dataKey="date" fontSize={11} stroke={axisColor} tickLine={false} axisLine={false} />
              <YAxis fontSize={11} stroke={axisColor} tickLine={false} axisLine={false} allowDecimals={false} />
              <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: tooltipStyle.color }} />
              <Line type="monotone" dataKey="suspicious_transactions" stroke="#dc2626" strokeWidth={2} dot={false} activeDot={{ r: 5 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {!isAnalyst && !isManager && (
          <div className="app-card">
            <h2 className="font-semibold mb-3 text-slate-800 dark:text-slate-100">Recent Alerts</h2>
            <ul className="divide-y divide-slate-100 dark:divide-white/5">
              {recentAlerts.map((a) => (
                <li key={a.id} className="py-2 flex items-center justify-between text-sm text-slate-700 dark:text-slate-200">
                  <span>{a.title}</span>
                  <span className="text-xs text-slate-500 dark:text-slate-400">{a.status}</span>
                </li>
              ))}
              {recentAlerts.length === 0 && <li className="py-2 text-sm text-slate-400 dark:text-slate-500">No alerts yet.</li>}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
