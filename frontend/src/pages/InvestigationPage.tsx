import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../services/api";
import { useAuth } from "../hooks/useAuth";
import RiskBadge from "../components/RiskBadge";
import StatCard from "../components/StatCard";
import AIInvestigationAssistant from "../components/AIInvestigationAssistant";
import type { CaseAlertSummary, CaseFingerprintUsage, CaseTransactionSummary, Feedback, InvestigationCase } from "../types";

function fmtDateTime(value: string) {
  return new Date(value).toLocaleString();
}

function fmtAmount(amount: number, currency: string) {
  return `${currency} ${amount.toLocaleString()}`;
}

function SectionCard({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-xl shadow-card border border-primary-100/70 p-4 dark:bg-[#141a2e] dark:border-white/10 dark:shadow-none">
      <h2 className="font-semibold mb-1">{title}</h2>
      {subtitle && <p className="text-xs text-slate-500 mb-3 dark:text-slate-400">{subtitle}</p>}
      {children}
    </div>
  );
}

function TxnTable({ rows, emptyText, highlightId }: { rows: CaseTransactionSummary[]; emptyText: string; highlightId?: string }) {
  if (rows.length === 0) return <p className="text-sm text-slate-400 dark:text-slate-500">{emptyText}</p>;
  return (
    <div className="overflow-x-auto -mx-1">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
            <th className="px-1 py-1.5">Transaction</th>
            <th className="px-1 py-1.5">Customer</th>
            <th className="px-1 py-1.5">Amount</th>
            <th className="px-1 py-1.5">Device</th>
            <th className="px-1 py-1.5">IP</th>
            <th className="px-1 py-1.5">Location</th>
            <th className="px-1 py-1.5">When</th>
            <th className="px-1 py-1.5">Risk</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-white/5">
          {rows.map((t) => (
            <tr key={t.id} className={t.id === highlightId ? "bg-amber-50 dark:bg-amber-500/10" : undefined}>
              <td className="px-1 py-1.5">
                <Link to={`/transactions/${t.id}`} className="text-slate-900 font-medium hover:underline dark:text-slate-100">
                  {t.transaction_id}
                </Link>
              </td>
              <td className="px-1 py-1.5">
                {t.customer_id ? (
                  <Link to={`/customers/${t.customer_id}`} className="hover:underline">
                    {t.customer_id}
                  </Link>
                ) : (
                  "—"
                )}
              </td>
              <td className="px-1 py-1.5">{fmtAmount(t.amount, t.currency)}</td>
              <td className="px-1 py-1.5 text-slate-500 dark:text-slate-400">{t.device_id || "—"}</td>
              <td className="px-1 py-1.5 text-slate-500 dark:text-slate-400">{t.ip_address || "—"}</td>
              <td className="px-1 py-1.5 text-slate-500 dark:text-slate-400">{t.location || "—"}</td>
              <td className="px-1 py-1.5 text-slate-500 dark:text-slate-400">{fmtDateTime(t.transaction_datetime)}</td>
              <td className="px-1 py-1.5">
                <RiskBadge level={t.risk_level} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function FingerprintList({ items, label }: { items: CaseFingerprintUsage[]; label: string }) {
  if (items.length === 0) return <p className="text-sm text-slate-400 dark:text-slate-500">No {label.toLowerCase()} on record.</p>;
  return (
    <ul className="space-y-2 text-sm">
      {items.map((item) => (
        <li key={item.value} className="flex items-center justify-between bg-slate-50 rounded-lg px-3 py-2 dark:bg-white/5">
          <div>
            <div className="font-medium text-slate-800 dark:text-slate-200">{item.value}</div>
            <div className="text-xs text-slate-500 dark:text-slate-400">
              {item.transaction_count} txn{item.transaction_count === 1 ? "" : "s"} · first {fmtDateTime(item.first_seen)} · last {fmtDateTime(item.last_seen)}
              {item.device_type ? ` · ${item.device_type}` : ""}
              {item.city || item.country ? ` · ${[item.city, item.country].filter(Boolean).join(", ")}` : ""}
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
}

function AlertList({ alerts, currentAlertId }: { alerts: CaseAlertSummary[]; currentAlertId: string }) {
  if (alerts.length === 0) return <p className="text-sm text-slate-400 dark:text-slate-500">No related alerts.</p>;
  return (
    <ul className="space-y-2">
      {alerts.map((a) => (
        <li key={a.id}>
          <Link
            to={a.id === currentAlertId ? "#" : `/alerts/${a.id}`}
            className="flex items-center justify-between bg-slate-50 rounded-lg px-3 py-2 text-sm hover:bg-slate-100 dark:bg-white/5 dark:hover:bg-white/10"
          >
            <div>
              <div className="font-medium text-slate-800 dark:text-slate-200">{a.title}</div>
              <div className="text-xs text-slate-500 dark:text-slate-400">
                {a.customer_id} · {fmtDateTime(a.created_at)}
              </div>
            </div>
            <div className="flex items-center gap-2">
              <RiskBadge level={a.severity} />
              <span className="text-xs text-slate-500 dark:text-slate-400">{a.status}</span>
            </div>
          </Link>
        </li>
      ))}
    </ul>
  );
}

export default function InvestigationPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const canInvestigate = user?.role === "ADMIN" || user?.role === "ANALYST";

  const [data, setData] = useState<InvestigationCase | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [noteText, setNoteText] = useState("");
  const [submittingNote, setSubmittingNote] = useState(false);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [feedbackComment, setFeedbackComment] = useState("");
  const [submittingFeedback, setSubmittingFeedback] = useState(false);
  const [feedbackError, setFeedbackError] = useState<string | null>(null);

  const load = useCallback(() => {
    if (!id) return;
    api
      .get(`/investigation/case/${id}`)
      .then((r) => setData(r.data))
      .catch(() => setLoadError(true));
    api
      .get(`/alerts/${id}/feedback`)
      .then((r) => setFeedback(r.data?.[0] ?? null))
      .catch(() => {
        // Non-fatal: the page still works without showing prior feedback.
      });
  }, [id]);

  useEffect(load, [load]);

  async function submitNote(e: React.FormEvent) {
    e.preventDefault();
    if (!noteText.trim() || !id) return;
    setSubmittingNote(true);
    try {
      await api.post(`/alerts/${id}/notes`, { note: noteText });
      setNoteText("");
      load();
    } finally {
      setSubmittingNote(false);
    }
  }

  async function markOutcome(result: "CONFIRMED_FRAUD" | "FALSE_POSITIVE") {
    setFeedbackError(null);
    setSubmittingFeedback(true);
    try {
      const resp = await api.post(`/alerts/${id}/feedback`, {
        actual_result: result,
        comments: feedbackComment.trim() || undefined,
      });
      setFeedback(resp.data);
      load();
    } catch (err: any) {
      const message = err?.response?.data?.error?.message || "Could not record that outcome.";
      setFeedbackError(message);
      if (err?.response?.status === 409) {
        // Someone else already labeled this alert -- refresh so the UI reflects it.
        load();
      }
    } finally {
      setSubmittingFeedback(false);
    }
  }

  if (loadError) return <p className="text-red-600 text-sm dark:text-red-400">Could not load this investigation. It may not exist, or you may not have access.</p>;
  if (!data) return <p className="text-slate-400 dark:text-slate-500">Loading...</p>;

  const { alert, customer, transaction } = data;

  return (
    <div>
      <div className="flex items-center gap-3 mb-1 flex-wrap">
        <h1 className="text-2xl font-bold">Investigation: {alert.title}</h1>
        <RiskBadge level={alert.severity} />
        <span className="text-xs text-slate-500 dark:text-slate-400">{alert.status}</span>
      </div>
      <p className="text-sm text-slate-500 mb-6 dark:text-slate-400">
        Customer{" "}
        <Link to={`/customers/${customer.customer_id}`} className="font-medium text-slate-700 hover:underline dark:text-slate-300">
          {customer.customer_id}
        </Link>{" "}
        · Transaction{" "}
        <Link to={`/transactions/${transaction.id}`} className="font-medium text-slate-700 hover:underline dark:text-slate-300">
          {transaction.transaction_id}
        </Link>{" "}
        · {fmtDateTime(transaction.transaction_datetime)}
      </p>

      {!canInvestigate && (
        <div className="mb-6 text-sm bg-amber-50 text-amber-800 px-4 py-2 rounded-lg dark:bg-amber-500/10 dark:text-amber-300">
          You have view-only access to this alert. Investigation actions (notes, fraud decisions,
          the AI assistant) are available to Admins and Analysts.
        </div>
      )}

      {/* Customer info */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard label="Customer Risk Score" value={customer.risk_score.toFixed(0)} />
        <StatCard label="Total Transactions" value={customer.total_transactions} />
        <StatCard label="Suspicious Transactions" value={customer.suspicious_transactions} accent="text-amber-600" />
        <StatCard label="Previous Fraud Reports" value={customer.previous_fraud_reports} accent="text-red-600" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Flagged transaction + risk factors + AI explanation */}
        <SectionCard title="Flagged Transaction & Risk Factors">
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm mb-3">
            <dt className="text-slate-500 dark:text-slate-400">Amount</dt>
            <dd>{fmtAmount(transaction.amount, transaction.currency)}</dd>
            <dt className="text-slate-500 dark:text-slate-400">Payment method</dt>
            <dd>{transaction.payment_method || "—"}</dd>
            <dt className="text-slate-500 dark:text-slate-400">Device</dt>
            <dd>{transaction.device_id || "—"}</dd>
            <dt className="text-slate-500 dark:text-slate-400">IP address</dt>
            <dd>{transaction.ip_address || "—"}</dd>
            <dt className="text-slate-500 dark:text-slate-400">Location</dt>
            <dd>{transaction.location || "—"}</dd>
            <dt className="text-slate-500 dark:text-slate-400">Decision</dt>
            <dd>{transaction.decision}</dd>
            <dt className="text-slate-500 dark:text-slate-400">Risk score</dt>
            <dd>
              {transaction.risk_score.toFixed(0)}/100 (<RiskBadge level={transaction.risk_level} />)
            </dd>
          </dl>
          {data.risk_factors.length > 0 && (
            <div className="mb-3">
              <div className="text-xs uppercase tracking-wide text-slate-500 mb-1 dark:text-slate-400">Risk factors</div>
              <ul className="list-disc list-inside text-sm text-slate-700 space-y-0.5 dark:text-slate-300">
                {data.risk_factors.map((f, i) => (
                  <li key={i}>{f}</li>
                ))}
              </ul>
            </div>
          )}
          {data.ai_explanation && (
            <div className="mb-3">
              <div className="text-xs uppercase tracking-wide text-slate-500 mb-1 dark:text-slate-400">AI Explanation</div>
              <pre className="whitespace-pre-wrap text-sm text-slate-700 font-sans bg-slate-50 rounded-lg px-3 py-2 dark:text-slate-300 dark:bg-white/5">{data.ai_explanation}</pre>
            </div>
          )}
          {canInvestigate && (
            <div className="mt-3">
              {feedback ? (
                <div
                  className={`text-sm rounded-lg px-3 py-2 ${
                    feedback.actual_result === "CONFIRMED_FRAUD"
                      ? "bg-red-50 text-red-800 dark:bg-red-500/10 dark:text-red-300"
                      : "bg-slate-100 text-slate-700 dark:bg-white/10 dark:text-slate-300"
                  }`}
                >
                  <div className="font-medium">
                    Marked {feedback.actual_result === "CONFIRMED_FRAUD" ? "Confirmed Fraud" : "False Positive"}
                    {feedback.analyst_name ? ` by ${feedback.analyst_name}` : ""}
                  </div>
                  <div className="text-xs opacity-75">{fmtDateTime(feedback.created_at)}</div>
                  {feedback.comments && <div className="text-xs mt-1">{feedback.comments}</div>}
                  <div className="text-xs opacity-75 mt-1">
                    This outcome is stored as labeled data for improving the fraud model.
                  </div>
                </div>
              ) : (
                <>
                  <input
                    className="w-full border border-slate-200 rounded-lg px-3 py-1.5 text-sm mb-2 focus:outline-none focus:ring-2 focus:ring-primary-500/30 focus:border-primary-400 transition bg-white dark:bg-white/5 dark:border-white/10 dark:text-slate-100 dark:placeholder:text-slate-500"
                    placeholder="Optional comment (e.g. what confirmed this)..."
                    value={feedbackComment}
                    onChange={(e) => setFeedbackComment(e.target.value)}
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={() => markOutcome("CONFIRMED_FRAUD")}
                      disabled={submittingFeedback}
                      className="bg-red-600 text-white text-sm px-3 py-1.5 rounded-lg disabled:opacity-50"
                    >
                      Confirm Fraud
                    </button>
                    <button
                      onClick={() => markOutcome("FALSE_POSITIVE")}
                      disabled={submittingFeedback}
                      className="bg-slate-200 text-sm px-3 py-1.5 rounded-lg disabled:opacity-50 dark:bg-white/10 dark:text-slate-200"
                    >
                      False Positive
                    </button>
                  </div>
                  {feedbackError && <p className="text-xs text-red-600 mt-2 dark:text-red-400">{feedbackError}</p>}
                </>
              )}
            </div>
          )}
        </SectionCard>

        {canInvestigate && (
          <AIInvestigationAssistant
            alertId={data.alert.id}
            customerId={data.customer.customer_id}
            deviceId={transaction.device_id || undefined}
          />
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        <SectionCard title="Devices" subtitle="Used by this customer">
          <FingerprintList items={data.devices} label="devices" />
        </SectionCard>
        <SectionCard title="IP Addresses" subtitle="Used by this customer">
          <FingerprintList items={data.ip_addresses} label="IP addresses" />
        </SectionCard>
        <SectionCard title="Locations" subtitle="Used by this customer">
          <FingerprintList items={data.locations} label="locations" />
        </SectionCard>
      </div>

      <div className="grid grid-cols-1 gap-6 mb-6">
        <SectionCard title="Transaction History" subtitle={`Recent transactions from ${customer.customer_id}`}>
          <TxnTable rows={data.transaction_history} emptyText="No transaction history." highlightId={transaction.id} />
        </SectionCard>

        <SectionCard title="Related Transactions" subtitle="Other customers sharing this transaction's device, IP, or location">
          <TxnTable rows={data.related_transactions} emptyText="No related transactions from other customers were found." />
        </SectionCard>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <SectionCard title="Related Alerts">
          <AlertList alerts={data.related_alerts} currentAlertId={alert.id} />
        </SectionCard>

        {canInvestigate && (
          <SectionCard title="Investigation Notes">
            <ul className="mb-3 space-y-2 max-h-72 overflow-y-auto">
              {data.investigation_notes.map((n) => (
                <li key={n.id} className="text-sm bg-slate-50 rounded-lg px-3 py-2 dark:bg-white/5">
                  <div>{n.note}</div>
                  <div className="text-xs text-slate-400 mt-1 dark:text-slate-500">
                    {n.analyst_name || "Analyst"} · {fmtDateTime(n.created_at)}
                  </div>
                </li>
              ))}
              {data.investigation_notes.length === 0 && <li className="text-sm text-slate-400 dark:text-slate-500">No notes yet.</li>}
            </ul>
            <form onSubmit={submitNote} className="flex gap-2">
              <input
                className="flex-1 border border-slate-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/30 focus:border-primary-400 transition bg-white dark:bg-white/5 dark:border-white/10 dark:text-slate-100 dark:placeholder:text-slate-500"
                placeholder="Add an investigation note..."
                value={noteText}
                onChange={(e) => setNoteText(e.target.value)}
              />
              <button disabled={submittingNote} className="bg-slate-200 text-sm px-3 py-1.5 rounded-lg disabled:opacity-50 dark:bg-white/10 dark:text-slate-200">
                Add
              </button>
            </form>
          </SectionCard>
        )}
      </div>
    </div>
  );
}
