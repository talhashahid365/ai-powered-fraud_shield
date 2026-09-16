import { useEffect, useState } from "react";
import { api } from "../services/api";
import type { ApiKey, ApiKeyCreated } from "../types";

export default function ApiKeysPage() {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [businessName, setBusinessName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [justCreated, setJustCreated] = useState<ApiKeyCreated | null>(null);
  const [copied, setCopied] = useState(false);

  function load() {
    api.get("/api-keys").then((r) => setKeys(r.data));
  }

  useEffect(load, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!businessName.trim()) {
      setError("Business name is required.");
      return;
    }
    try {
      const { data } = await api.post<ApiKeyCreated>("/api-keys", { business_name: businessName.trim() });
      setJustCreated(data);
      setCopied(false);
      setBusinessName("");
      load();
    } catch {
      setError("Could not create API key. Try again.");
    }
  }

  async function handleRevoke(key: ApiKey) {
    if (!confirm(`Revoke the API key for "${key.business_name}"? Any external system using it will immediately stop working.`)) return;
    await api.delete(`/api-keys/${key.id}`);
    load();
  }

  async function copyKey() {
    if (!justCreated) return;
    await navigator.clipboard.writeText(justCreated.api_key);
    setCopied(true);
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold">External Business API Keys</h1>
        <p className="text-sm text-slate-500 mt-1 dark:text-slate-400">
          Issue keys so external e-commerce/payment systems can call{" "}
          <code className="bg-slate-100 px-1 rounded dark:bg-white/10">POST /api/transactions</code>,{" "}
          <code className="bg-slate-100 px-1 rounded dark:bg-white/10">POST /api/risk-check</code>, and related
          endpoints directly, without a dashboard login.
        </p>
      </div>

      {justCreated && (
        <div className="bg-amber-50 border border-amber-300 rounded-xl p-4 mb-6 dark:bg-amber-500/10 dark:border-amber-500/30">
          <p className="text-sm font-semibold text-amber-900 mb-1 dark:text-amber-300">
            API key created for "{justCreated.business_name}"
          </p>
          <p className="text-xs text-amber-800 mb-2 dark:text-amber-300">
            Copy it now — for security, it will never be shown again.
          </p>
          <div className="flex items-center gap-2">
            <code className="flex-1 bg-white border border-amber-200 rounded-lg px-3 py-2 text-sm font-mono break-all dark:bg-[#0b0e1c] dark:border-amber-500/30 dark:text-slate-100">
              {justCreated.api_key}
            </code>
            <button
              onClick={copyKey}
              className="bg-primary-600 text-white text-xs px-3 py-2 rounded-lg hover:bg-primary-700 whitespace-nowrap"
            >
              {copied ? "Copied!" : "Copy"}
            </button>
          </div>
          <button
            onClick={() => setJustCreated(null)}
            className="text-xs text-amber-700 hover:text-amber-900 mt-2 dark:text-amber-400 dark:hover:text-amber-300"
          >
            Dismiss
          </button>
        </div>
      )}

      <form onSubmit={handleCreate} className="bg-white border border-primary-100/70 rounded-xl p-4 mb-6 flex items-end gap-3 dark:bg-[#141a2e] dark:border-white/10">
        <div className="flex-1">
          <label className="block text-xs font-medium text-slate-500 mb-1 dark:text-slate-400">Business / System Name</label>
          <input
            className="w-full border border-slate-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/30 focus:border-primary-400 transition bg-white dark:bg-white/5 dark:border-white/10 dark:text-slate-100 dark:placeholder:text-slate-500"
            value={businessName}
            onChange={(e) => setBusinessName(e.target.value)}
            placeholder="e.g. Acme E-Commerce Checkout"
          />
        </div>
        <button className="bg-primary-600 text-white text-sm px-4 py-1.5 rounded-lg hover:bg-primary-700">
          + Generate Key
        </button>
      </form>
      {error && <p className="text-red-600 text-sm mb-4 dark:text-red-400">{error}</p>}

      <div className="bg-white rounded-xl shadow-card border border-primary-100/70 overflow-hidden dark:bg-[#141a2e] dark:border-white/10 dark:shadow-none">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-500 text-left dark:bg-white/5 dark:text-slate-400">
            <tr>
              <th className="px-4 py-2">Business</th>
              <th className="px-4 py-2">Key Prefix</th>
              <th className="px-4 py-2">Status</th>
              <th className="px-4 py-2">Last Used</th>
              <th className="px-4 py-2">Created</th>
              <th className="px-4 py-2"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-white/5">
            {keys.map((k) => (
              <tr key={k.id} className="hover:bg-slate-50 dark:hover:bg-white/5">
                <td className="px-4 py-2 font-medium">{k.business_name}</td>
                <td className="px-4 py-2 font-mono text-xs text-slate-600 dark:text-slate-400">{k.key_prefix}...</td>
                <td className="px-4 py-2">
                  <span
                    className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
                      k.is_active
                        ? "bg-green-100 text-green-800 dark:bg-green-500/10 dark:text-green-400"
                        : "bg-slate-200 text-slate-600 dark:bg-white/10 dark:text-slate-300"
                    }`}
                  >
                    {k.is_active ? "Active" : "Revoked"}
                  </span>
                </td>
                <td className="px-4 py-2 text-xs text-slate-500 dark:text-slate-400">
                  {k.last_used_at ? new Date(k.last_used_at).toLocaleString() : "Never"}
                </td>
                <td className="px-4 py-2 text-xs text-slate-500 dark:text-slate-400">{new Date(k.created_at).toLocaleDateString()}</td>
                <td className="px-4 py-2 text-right">
                  {k.is_active && (
                    <button onClick={() => handleRevoke(k)} className="text-red-500 hover:text-red-700 text-xs dark:text-red-400 dark:hover:text-red-300">
                      Revoke
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {keys.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-6 text-center text-slate-400 dark:text-slate-500">No API keys issued yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
