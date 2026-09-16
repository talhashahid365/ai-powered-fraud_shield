import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../services/api";
import { useAuth } from "../hooks/useAuth";
import RiskBadge from "../components/RiskBadge";
import type { Transaction } from "../types";

const EMPTY_FORM = {
  transaction_id: "",
  customer_id: "",
  amount: "",
  currency: "USD",
  transaction_datetime: "",
  payment_method: "",
  ip_address: "",
  device_id: "",
  location: "",
};

function AddTransactionModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function set<K extends keyof typeof EMPTY_FORM>(key: K, value: string) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!form.transaction_id.trim() || !form.customer_id.trim() || !form.amount) {
      setError("Transaction ID, Customer ID, and Amount are required.");
      return;
    }
    setSubmitting(true);
    try {
      await api.post("/transactions", {
        transaction_id: form.transaction_id.trim(),
        customer_id: form.customer_id.trim(),
        amount: parseFloat(form.amount),
        currency: form.currency || "USD",
        transaction_datetime: form.transaction_datetime ? new Date(form.transaction_datetime).toISOString() : undefined,
        payment_method: form.payment_method || undefined,
        ip_address: form.ip_address || undefined,
        device_id: form.device_id || undefined,
        location: form.location || undefined,
      });
      onCreated();
      onClose();
    } catch (err: any) {
      setError(err?.response?.data?.error?.message || "Failed to create transaction.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-lg w-full max-w-lg p-6 dark:bg-[#141a2e] dark:shadow-none dark:border dark:border-white/10">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold">Add Transaction</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 text-xl leading-none dark:text-slate-500 dark:hover:text-slate-300">&times;</button>
        </div>

        {error && <div className="mb-3 text-sm bg-red-50 text-red-700 px-3 py-2 rounded-lg dark:bg-red-500/10 dark:text-red-400">{error}</div>}

        <form onSubmit={handleSubmit} className="grid grid-cols-2 gap-3">
          <div className="col-span-1">
            <label className="block text-xs text-slate-500 mb-1 dark:text-slate-400">Transaction ID *</label>
            <input className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/30 focus:border-primary-400 transition bg-white dark:bg-white/5 dark:border-white/10 dark:text-slate-100 dark:placeholder:text-slate-500" value={form.transaction_id} onChange={(e) => set("transaction_id", e.target.value)} required />
          </div>
          <div className="col-span-1">
            <label className="block text-xs text-slate-500 mb-1 dark:text-slate-400">Customer ID *</label>
            <input className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/30 focus:border-primary-400 transition bg-white dark:bg-white/5 dark:border-white/10 dark:text-slate-100 dark:placeholder:text-slate-500" value={form.customer_id} onChange={(e) => set("customer_id", e.target.value)} required />
          </div>
          <div className="col-span-1">
            <label className="block text-xs text-slate-500 mb-1 dark:text-slate-400">Amount *</label>
            <input type="number" step="0.01" className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/30 focus:border-primary-400 transition bg-white dark:bg-white/5 dark:border-white/10 dark:text-slate-100 dark:placeholder:text-slate-500" value={form.amount} onChange={(e) => set("amount", e.target.value)} required />
          </div>
          <div className="col-span-1">
            <label className="block text-xs text-slate-500 mb-1 dark:text-slate-400">Currency</label>
            <input className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/30 focus:border-primary-400 transition bg-white dark:bg-white/5 dark:border-white/10 dark:text-slate-100 dark:placeholder:text-slate-500" value={form.currency} onChange={(e) => set("currency", e.target.value)} />
          </div>
          <div className="col-span-2">
            <label className="block text-xs text-slate-500 mb-1 dark:text-slate-400">Date/Time</label>
            <input type="datetime-local" className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/30 focus:border-primary-400 transition bg-white dark:bg-white/5 dark:border-white/10 dark:text-slate-100 dark:placeholder:text-slate-500" value={form.transaction_datetime} onChange={(e) => set("transaction_datetime", e.target.value)} />
          </div>
          <div className="col-span-1">
            <label className="block text-xs text-slate-500 mb-1 dark:text-slate-400">Payment Method</label>
            <input className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/30 focus:border-primary-400 transition bg-white dark:bg-white/5 dark:border-white/10 dark:text-slate-100 dark:placeholder:text-slate-500" placeholder="CARD, WALLET, ..." value={form.payment_method} onChange={(e) => set("payment_method", e.target.value)} />
          </div>
          <div className="col-span-1">
            <label className="block text-xs text-slate-500 mb-1 dark:text-slate-400">Location</label>
            <input className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/30 focus:border-primary-400 transition bg-white dark:bg-white/5 dark:border-white/10 dark:text-slate-100 dark:placeholder:text-slate-500" value={form.location} onChange={(e) => set("location", e.target.value)} />
          </div>
          <div className="col-span-1">
            <label className="block text-xs text-slate-500 mb-1 dark:text-slate-400">IP Address</label>
            <input className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/30 focus:border-primary-400 transition bg-white dark:bg-white/5 dark:border-white/10 dark:text-slate-100 dark:placeholder:text-slate-500" value={form.ip_address} onChange={(e) => set("ip_address", e.target.value)} />
          </div>
          <div className="col-span-1">
            <label className="block text-xs text-slate-500 mb-1 dark:text-slate-400">Device ID</label>
            <input className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/30 focus:border-primary-400 transition bg-white dark:bg-white/5 dark:border-white/10 dark:text-slate-100 dark:placeholder:text-slate-500" value={form.device_id} onChange={(e) => set("device_id", e.target.value)} />
          </div>

          <div className="col-span-2 flex justify-end gap-2 mt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 rounded-lg text-sm border border-slate-200 dark:border-white/10 dark:text-slate-200">Cancel</button>
            <button type="submit" disabled={submitting} className="px-4 py-2 rounded-lg text-sm bg-primary-600 text-white disabled:opacity-50">
              {submitting ? "Saving..." : "Save Transaction"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function TransactionsPage() {
  const { user } = useAuth();
  const canImport = user?.role === "ADMIN" || user?.role === "BUSINESS_MANAGER";
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [search, setSearch] = useState("");
  const [riskLevel, setRiskLevel] = useState("");
  const [paymentMethod, setPaymentMethod] = useState("");
  const [location, setLocation] = useState("");
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [importSummary, setImportSummary] = useState<string | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);

  // Accepts an explicit page so callers that also just reset `page` to 1
  // (e.g. after a search or a CSV import) can refetch immediately instead of
  // depending on the setPage(1) state update landing first - setState is
  // async, so `load()` called right after `setPage(1)` would otherwise still
  // read the OLD `page` value from this closure, and if the user was already
  // on page 1 the state wouldn't even change, so nothing would refetch at all.
  function load(pageOverride?: number) {
    api
      .get("/transactions", {
        params: {
          page: pageOverride ?? page,
          page_size: 20,
          search: search || undefined,
          risk_level: riskLevel || undefined,
          payment_method: paymentMethod || undefined,
          location: location || undefined,
        },
      })
      .then((r) => {
        setTransactions(r.data.data);
        setTotal(r.data.total);
      });
  }

  useEffect(load, [page, riskLevel, paymentMethod, location]);

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setPage(1);
    load(1);
  }

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setImportError(null);
    setImportSummary(null);
    const formData = new FormData();
    formData.append("file", file);
    try {
      const { data } = await api.post("/transactions/import-csv", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setImportSummary(
        `Imported ${data.successful_rows}/${data.total_rows} rows (${data.failed_rows} failed, ${data.duplicate_rows} duplicates).` +
          (data.errors?.length ? ` First error: ${data.errors[0]}` : "")
      );
      // New rows sort newest-first, so jump back to page 1 to actually see
      // them - and refetch directly rather than relying on the page-change
      // effect, since it won't fire if the user was already on page 1.
      setPage(1);
      load(1);
    } catch (err: any) {
      // Previously an upload failure (network error, wrong host, expired
      // session, server error) threw silently here with no try/catch: the
      // browser showed nothing, so a failed import looked identical to a
      // successful one that just "didn't add records".
      setImportError(err?.response?.data?.error?.message || "CSV import failed. Please check the file and try again.");
    } finally {
      e.target.value = "";
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Transactions</h1>
        {canImport && (
          <div className="flex gap-2">
            <button
              onClick={() => setShowAddModal(true)}
              className="bg-white border border-slate-200 text-slate-700 text-sm px-4 py-2 rounded-lg hover:bg-slate-50 dark:bg-white/5 dark:border-white/10 dark:text-slate-200 dark:hover:bg-white/10"
            >
              + Add Transaction
            </button>
            <label className="bg-primary-600 text-white text-sm px-4 py-2 rounded-lg cursor-pointer hover:bg-primary-700">
              Import CSV
              <input type="file" accept=".csv" className="hidden" onChange={handleUpload} />
            </label>
          </div>
        )}
      </div>

      {importSummary && <div className="mb-4 text-sm bg-blue-50 text-blue-800 px-4 py-2 rounded-lg dark:bg-blue-500/10 dark:text-blue-300">{importSummary}</div>}
      {importError && <div className="mb-4 text-sm bg-red-50 text-red-700 px-4 py-2 rounded-lg dark:bg-red-500/10 dark:text-red-400">{importError}</div>}

      {showAddModal && (
        <AddTransactionModal
          onClose={() => setShowAddModal(false)}
          onCreated={() => {
            setImportSummary(null);
            setImportError(null);
            setPage(1);
            load(1);
          }}
        />
      )}

      <form onSubmit={handleSearch} className="flex flex-wrap gap-3 mb-4">
        <input
          className="border border-slate-200 rounded-lg px-3 py-2 text-sm flex-1 focus:outline-none focus:ring-2 focus:ring-primary-500/30 focus:border-primary-400 transition min-w-[200px] bg-white dark:bg-white/5 dark:border-white/10 dark:text-slate-100 dark:placeholder:text-slate-500"
          placeholder="Search transaction or customer ID..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select className="border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/30 focus:border-primary-400 transition bg-white dark:bg-white/5 dark:border-white/10 dark:text-slate-100 dark:placeholder:text-slate-500" value={riskLevel} onChange={(e) => setRiskLevel(e.target.value)}>
          <option value="">All Risk Levels</option>
          <option value="LOW">Low</option>
          <option value="MEDIUM">Medium</option>
          <option value="HIGH">High</option>
        </select>
        <input
          className="border border-slate-200 rounded-lg px-3 py-2 text-sm w-40 focus:outline-none focus:ring-2 focus:ring-primary-500/30 focus:border-primary-400 transition bg-white dark:bg-white/5 dark:border-white/10 dark:text-slate-100 dark:placeholder:text-slate-500"
          placeholder="Payment method"
          value={paymentMethod}
          onChange={(e) => setPaymentMethod(e.target.value)}
        />
        <input
          className="border border-slate-200 rounded-lg px-3 py-2 text-sm w-40 focus:outline-none focus:ring-2 focus:ring-primary-500/30 focus:border-primary-400 transition bg-white dark:bg-white/5 dark:border-white/10 dark:text-slate-100 dark:placeholder:text-slate-500"
          placeholder="Location"
          value={location}
          onChange={(e) => setLocation(e.target.value)}
        />
        <button className="bg-slate-200 px-4 py-2 rounded-lg text-sm dark:bg-white/10 dark:text-slate-200">Search</button>
      </form>

      <div className="bg-white rounded-xl shadow-card border border-primary-100/70 overflow-hidden dark:bg-[#141a2e] dark:border-white/10 dark:shadow-none">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-500 text-left dark:bg-white/5 dark:text-slate-400">
            <tr>
              <th className="px-4 py-2">Transaction</th>
              <th className="px-4 py-2">Customer</th>
              <th className="px-4 py-2">Amount</th>
              <th className="px-4 py-2">Risk</th>
              <th className="px-4 py-2">Decision</th>
              <th className="px-4 py-2">Date</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-white/5">
            {transactions.map((t) => (
              <tr key={t.id} className="hover:bg-slate-50 dark:hover:bg-white/5">
                <td className="px-4 py-2">
                  <Link to={`/transactions/${t.id}`} className="text-primary-600 hover:underline">{t.transaction_id}</Link>
                </td>
                <td className="px-4 py-2">{t.customer_id}</td>
                <td className="px-4 py-2">{t.currency} {t.amount.toLocaleString()}</td>
                <td className="px-4 py-2"><RiskBadge level={t.risk_level} /></td>
                <td className="px-4 py-2">{t.decision}</td>
                <td className="px-4 py-2 text-slate-500 dark:text-slate-400">{new Date(t.transaction_datetime).toLocaleString()}</td>
              </tr>
            ))}
            {transactions.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-6 text-center text-slate-400 dark:text-slate-500">No transactions found.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="flex justify-between items-center mt-4 text-sm text-slate-500 dark:text-slate-400">
        <span>{total} total transactions</span>
        <div className="flex gap-2">
          <button disabled={page === 1} onClick={() => setPage((p) => p - 1)} className="px-3 py-1 border rounded disabled:opacity-40">Prev</button>
          <span>Page {page}</span>
          <button disabled={page * 20 >= total} onClick={() => setPage((p) => p + 1)} className="px-3 py-1 border rounded disabled:opacity-40">Next</button>
        </div>
      </div>
    </div>
  );
}
