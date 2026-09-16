import { useEffect, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../services/api";
import RiskBadge from "../components/RiskBadge";
import StatCard from "../components/StatCard";

type TabKey =
  | "daily"
  | "monthly"
  | "high-risk-customers"
  | "high-risk-transactions"
  | "confirmed-fraud"
  | "false-positives"
  | "fraud-trends";

const TABS: { key: TabKey; label: string }[] = [
  { key: "daily", label: "Daily Fraud Activity" },
  { key: "monthly", label: "Monthly Fraud Activity" },
  { key: "high-risk-customers", label: "High-Risk Customers" },
  { key: "high-risk-transactions", label: "High-Risk Transactions" },
  { key: "confirmed-fraud", label: "Confirmed Fraud" },
  { key: "false-positives", label: "False Positives" },
  { key: "fraud-trends", label: "Fraud Trends" },
];

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

function formatMoney(n: number | null | undefined) {
  if (n === null || n === undefined) return "—";
  return n.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}

async function downloadReport(exportType: string, params: Record<string, any>) {
  const resp = await api.get(`/reports/export/${exportType}`, { params, responseType: "blob" });
  const disposition: string = resp.headers["content-disposition"] || "";
  const match = disposition.match(/filename="?([^"]+)"?/);
  const filename = match ? match[1] : `${exportType}.csv`;
  const url = URL.createObjectURL(resp.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function ExportButton({ exportType, params }: { exportType: string; params: Record<string, any> }) {
  const [busy, setBusy] = useState(false);
  return (
    <button
      onClick={async () => {
        setBusy(true);
        try {
          await downloadReport(exportType, params);
        } catch (e) {
          alert("Export failed. Please try again.");
        } finally {
          setBusy(false);
        }
      }}
      disabled={busy}
      className="bg-primary-600 text-white text-sm px-3 py-1.5 rounded-lg disabled:opacity-50"
    >
      {busy ? "Exporting…" : "Export CSV"}
    </button>
  );
}

function Panel({ children }: { children: React.ReactNode }) {
  return <div className="bg-white rounded-xl shadow-card border border-primary-100/70 p-4 dark:bg-[#141a2e] dark:border-white/10 dark:shadow-none">{children}</div>;
}

function EmptyRow({ colSpan, text }: { colSpan: number; text: string }) {
  return (
    <tr>
      <td colSpan={colSpan} className="py-4 text-center text-slate-400 dark:text-slate-500">
        {text}
      </td>
    </tr>
  );
}

// ---------------------------------------------------------------------------
// Daily fraud activity
// ---------------------------------------------------------------------------

function DailyTab() {
  const [date, setDate] = useState(todayISO());
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setError(null);
    api
      .get("/reports/daily-fraud-activity", { params: { date } })
      .then((r) => setData(r.data))
      .catch((e) => setError(e.response?.data?.error?.message || "Failed to load report"));
  }, [date]);

  return (
    <Panel>
      <div className="flex flex-wrap items-end justify-between gap-3 mb-4">
        <div>
          <label className="block text-xs text-slate-500 mb-1 dark:text-slate-400">Date</label>
          <input
            type="date"
            value={date}
            max={todayISO()}
            onChange={(e) => setDate(e.target.value)}
            className="border border-slate-200 rounded-lg px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/30 focus:border-primary-400 transition bg-white dark:bg-white/5 dark:border-white/10 dark:text-slate-100 dark:placeholder:text-slate-500"
          />
        </div>
        <ExportButton exportType="daily-fraud-activity" params={{ date }} />
      </div>

      {error && <p className="text-sm text-red-600 mb-3 dark:text-red-400">{error}</p>}

      {data ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard label="Total Transactions" value={data.total_transactions} />
          <StatCard label="Total Amount" value={formatMoney(data.total_amount)} />
          <StatCard label="High Risk" value={data.high_risk} accent="text-red-600" />
          <StatCard label="Medium Risk" value={data.medium_risk} accent="text-amber-600" />
          <StatCard label="Low Risk" value={data.low_risk} accent="text-green-600" />
          <StatCard label="Blocked" value={data.blocked} />
          <StatCard label="Alerts Created" value={data.alerts_created} />
          <StatCard label="Confirmed Fraud" value={data.confirmed_fraud} accent="text-red-600" />
          <StatCard label="False Positives" value={data.false_positives} />
        </div>
      ) : (
        !error && <p className="text-slate-400 text-sm dark:text-slate-500">Loading…</p>
      )}
    </Panel>
  );
}

// ---------------------------------------------------------------------------
// Monthly fraud activity
// ---------------------------------------------------------------------------

function MonthlyTab() {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setError(null);
    api
      .get("/reports/monthly-fraud-activity", { params: { year, month } })
      .then((r) => setData(r.data))
      .catch((e) => setError(e.response?.data?.error?.message || "Failed to load report"));
  }, [year, month]);

  return (
    <Panel>
      <div className="flex flex-wrap items-end justify-between gap-3 mb-4">
        <div className="flex gap-3">
          <div>
            <label className="block text-xs text-slate-500 mb-1 dark:text-slate-400">Year</label>
            <input
              type="number"
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
              className="border border-slate-200 rounded-lg px-2 py-1 text-sm w-24 focus:outline-none focus:ring-2 focus:ring-primary-500/30 focus:border-primary-400 transition bg-white dark:bg-white/5 dark:border-white/10 dark:text-slate-100 dark:placeholder:text-slate-500"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1 dark:text-slate-400">Month</label>
            <select
              value={month}
              onChange={(e) => setMonth(Number(e.target.value))}
              className="border border-slate-200 rounded-lg px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/30 focus:border-primary-400 transition bg-white dark:bg-white/5 dark:border-white/10 dark:text-slate-100 dark:placeholder:text-slate-500"
            >
              {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                <option key={m} value={m}>
                  {new Date(2000, m - 1, 1).toLocaleString(undefined, { month: "long" })}
                </option>
              ))}
            </select>
          </div>
        </div>
        <ExportButton exportType="monthly-fraud-activity" params={{ year, month }} />
      </div>

      {error && <p className="text-sm text-red-600 mb-3 dark:text-red-400">{error}</p>}

      {data ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard label="Total Transactions" value={data.total_transactions} />
          <StatCard label="Total Amount" value={formatMoney(data.total_amount)} />
          <StatCard label="High Risk" value={data.high_risk} accent="text-red-600" />
          <StatCard label="Medium Risk" value={data.medium_risk} accent="text-amber-600" />
          <StatCard label="Blocked" value={data.blocked} />
          <StatCard label="Alerts Created" value={data.alerts_created} />
          <StatCard label="Confirmed Fraud" value={data.confirmed_fraud} accent="text-red-600" />
          <StatCard label="False Positives" value={data.false_positives} />
          <StatCard
            label="Alert Precision"
            value={data.precision !== null ? `${(data.precision * 100).toFixed(0)}%` : "—"}
          />
        </div>
      ) : (
        !error && <p className="text-slate-400 text-sm dark:text-slate-500">Loading…</p>
      )}
    </Panel>
  );
}

// ---------------------------------------------------------------------------
// High-risk customers
// ---------------------------------------------------------------------------

function HighRiskCustomersTab() {
  const [rows, setRows] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api
      .get("/reports/high-risk-customers")
      .then((r) => setRows(r.data))
      .finally(() => setLoading(false));
  }, []);

  return (
    <Panel>
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-semibold">High-Risk Customers ({rows.length})</h2>
        <ExportButton exportType="high-risk-customers" params={{}} />
      </div>
      <table className="w-full text-sm">
        <thead className="text-slate-500 text-left dark:text-slate-400">
          <tr>
            <th className="py-1">Customer</th>
            <th className="py-1">Name</th>
            <th className="py-1">Risk Score</th>
            <th className="py-1">Total Txns</th>
            <th className="py-1">Suspicious Txns</th>
            <th className="py-1">Prior Fraud Reports</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-white/5">
          {rows.map((c) => (
            <tr key={c.customer_id}>
              <td className="py-1.5">{c.customer_id}</td>
              <td className="py-1.5">{c.name}</td>
              <td className="py-1.5">{c.risk_score.toFixed(0)}</td>
              <td className="py-1.5">{c.total_transactions}</td>
              <td className="py-1.5">{c.suspicious_transactions}</td>
              <td className="py-1.5">{c.previous_fraud_reports}</td>
            </tr>
          ))}
          {!loading && rows.length === 0 && <EmptyRow colSpan={6} text="No high-risk customers yet." />}
        </tbody>
      </table>
    </Panel>
  );
}

// ---------------------------------------------------------------------------
// High-risk transactions
// ---------------------------------------------------------------------------

function HighRiskTransactionsTab() {
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [rows, setRows] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const params: Record<string, any> = {};
    if (startDate) params.start_date = startDate;
    if (endDate) params.end_date = endDate;
    api
      .get("/reports/high-risk-transactions", { params })
      .then((r) => setRows(r.data))
      .finally(() => setLoading(false));
  }, [startDate, endDate]);

  return (
    <Panel>
      <div className="flex flex-wrap items-end justify-between gap-3 mb-3">
        <div className="flex gap-3">
          <div>
            <label className="block text-xs text-slate-500 mb-1 dark:text-slate-400">From</label>
            <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className="border border-slate-200 rounded-lg px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/30 focus:border-primary-400 transition bg-white dark:bg-white/5 dark:border-white/10 dark:text-slate-100 dark:placeholder:text-slate-500" />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1 dark:text-slate-400">To</label>
            <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} className="border border-slate-200 rounded-lg px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/30 focus:border-primary-400 transition bg-white dark:bg-white/5 dark:border-white/10 dark:text-slate-100 dark:placeholder:text-slate-500" />
          </div>
        </div>
        <ExportButton exportType="high-risk-transactions" params={{ start_date: startDate || undefined, end_date: endDate || undefined }} />
      </div>
      <table className="w-full text-sm">
        <thead className="text-slate-500 text-left dark:text-slate-400">
          <tr>
            <th className="py-1">Transaction</th>
            <th className="py-1">Customer</th>
            <th className="py-1">Amount</th>
            <th className="py-1">Risk Score</th>
            <th className="py-1">Decision</th>
            <th className="py-1">Date</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-white/5">
          {rows.map((t) => (
            <tr key={t.transaction_id}>
              <td className="py-1.5">{t.transaction_id}</td>
              <td className="py-1.5">{t.customer_id}</td>
              <td className="py-1.5">
                {t.amount.toLocaleString(undefined, { style: "currency", currency: t.currency || "USD" })}
              </td>
              <td className="py-1.5">{t.risk_score.toFixed(0)}</td>
              <td className="py-1.5">{t.decision}</td>
              <td className="py-1.5">{t.created_at}</td>
            </tr>
          ))}
          {!loading && rows.length === 0 && <EmptyRow colSpan={6} text="No high-risk transactions found." />}
        </tbody>
      </table>
    </Panel>
  );
}

// ---------------------------------------------------------------------------
// Confirmed fraud / False positives (shared shape)
// ---------------------------------------------------------------------------

function AlertOutcomeTab({ status }: { status: "confirmed-fraud" | "false-positives" }) {
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [rows, setRows] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const params: Record<string, any> = {};
    if (startDate) params.start_date = startDate;
    if (endDate) params.end_date = endDate;
    api
      .get(`/reports/${status}`, { params })
      .then((r) => setRows(r.data))
      .finally(() => setLoading(false));
  }, [status, startDate, endDate]);

  const label = status === "confirmed-fraud" ? "Confirmed Fraud" : "False Positives";

  return (
    <Panel>
      <div className="flex flex-wrap items-end justify-between gap-3 mb-3">
        <h2 className="font-semibold">
          {label} ({rows.length})
        </h2>
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="block text-xs text-slate-500 mb-1 dark:text-slate-400">From</label>
            <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className="border border-slate-200 rounded-lg px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/30 focus:border-primary-400 transition bg-white dark:bg-white/5 dark:border-white/10 dark:text-slate-100 dark:placeholder:text-slate-500" />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1 dark:text-slate-400">To</label>
            <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} className="border border-slate-200 rounded-lg px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/30 focus:border-primary-400 transition bg-white dark:bg-white/5 dark:border-white/10 dark:text-slate-100 dark:placeholder:text-slate-500" />
          </div>
          <ExportButton exportType={status} params={{ start_date: startDate || undefined, end_date: endDate || undefined }} />
        </div>
      </div>
      <table className="w-full text-sm">
        <thead className="text-slate-500 text-left dark:text-slate-400">
          <tr>
            <th className="py-1">Alert</th>
            <th className="py-1">Transaction</th>
            <th className="py-1">Customer</th>
            <th className="py-1">Severity</th>
            <th className="py-1">Amount</th>
            <th className="py-1">Reason</th>
            <th className="py-1">Date</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-white/5">
          {rows.map((a) => (
            <tr key={a.alert_id}>
              <td className="py-1.5 truncate max-w-[80px]" title={a.alert_id}>{a.alert_id.slice(0, 8)}</td>
              <td className="py-1.5">{a.transaction_id}</td>
              <td className="py-1.5">{a.customer_id}</td>
              <td className="py-1.5">
                <RiskBadge level={a.severity} />
              </td>
              <td className="py-1.5">{a.amount !== null ? formatMoney(a.amount) : "—"}</td>
              <td className="py-1.5 truncate max-w-[220px]" title={a.reason}>{a.reason}</td>
              <td className="py-1.5">{a.created_at}</td>
            </tr>
          ))}
          {!loading && rows.length === 0 && <EmptyRow colSpan={7} text={`No ${label.toLowerCase()} found for this range.`} />}
        </tbody>
      </table>
    </Panel>
  );
}

// ---------------------------------------------------------------------------
// Fraud trends
// ---------------------------------------------------------------------------

function FraudTrendsTab() {
  const [days, setDays] = useState(30);
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    api.get("/reports/fraud-trends", { params: { days } }).then((r) => setData(r.data));
  }, [days]);

  const directionColor =
    data?.trend_direction === "increasing"
      ? "text-red-600"
      : data?.trend_direction === "decreasing"
      ? "text-green-600"
      : "text-slate-600";

  return (
    <Panel>
      <div className="flex flex-wrap items-end justify-between gap-3 mb-4">
        <div>
          <label className="block text-xs text-slate-500 mb-1 dark:text-slate-400">Window</label>
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="border border-slate-200 rounded-lg px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/30 focus:border-primary-400 transition bg-white dark:bg-white/5 dark:border-white/10 dark:text-slate-100 dark:placeholder:text-slate-500"
          >
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
            <option value={180}>Last 180 days</option>
          </select>
        </div>
        <ExportButton exportType="fraud-trends" params={{ days }} />
      </div>

      {data ? (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
            <StatCard label="Confirmed Fraud" value={data.total_confirmed_fraud} accent="text-red-600" />
            <StatCard label="False Positives" value={data.total_false_positives} />
            <StatCard
              label="Trend"
              value={`${data.trend_direction} (${data.change_pct > 0 ? "+" : ""}${data.change_pct}%)`}
              accent={directionColor}
            />
            <StatCard label="Range" value={`${data.start_date} → ${data.end_date}`} />
          </div>

          <div style={{ width: "100%", height: 320 }}>
            <ResponsiveContainer>
              <LineChart data={data.daily}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="total_transactions" name="Transactions" stroke="#64748b" dot={false} />
                <Line type="monotone" dataKey="confirmed_fraud" name="Confirmed Fraud" stroke="#dc2626" dot={false} />
                <Line type="monotone" dataKey="false_positives" name="False Positives" stroke="#f59e0b" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </>
      ) : (
        <p className="text-slate-400 text-sm dark:text-slate-500">Loading…</p>
      )}
    </Panel>
  );
}

// ---------------------------------------------------------------------------
// Page shell
// ---------------------------------------------------------------------------

export default function ReportsPage() {
  const [tab, setTab] = useState<TabKey>("daily");

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Reports</h1>

      <div className="flex flex-wrap gap-2 mb-6">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`text-sm px-3 py-1.5 rounded-lg border ${
              tab === t.key
                ? "bg-primary-600 text-white border-primary-600"
                : "bg-white text-slate-700 border-primary-100/70 dark:bg-[#141a2e] dark:text-slate-300 dark:border-white/10"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "daily" && <DailyTab />}
      {tab === "monthly" && <MonthlyTab />}
      {tab === "high-risk-customers" && <HighRiskCustomersTab />}
      {tab === "high-risk-transactions" && <HighRiskTransactionsTab />}
      {tab === "confirmed-fraud" && <AlertOutcomeTab status="confirmed-fraud" />}
      {tab === "false-positives" && <AlertOutcomeTab status="false-positives" />}
      {tab === "fraud-trends" && <FraudTrendsTab />}
    </div>
  );
}
