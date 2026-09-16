import { useEffect, useState } from "react";
import { api } from "../services/api";
import type { Rule } from "../types";

const RULE_TYPES = [
  { value: "AMOUNT_THRESHOLD", label: "Amount Threshold", configHint: '{"threshold": 5000}' },
  { value: "VELOCITY", label: "Velocity (rapid transactions)", configHint: '{"max_count": 5, "window_minutes": 10}' },
  { value: "NEW_DEVICE_HIGH_VALUE", label: "New Device + High Value", configHint: '{"threshold": 1000}' },
  { value: "DEVICE_SHARING", label: "Device Sharing", configHint: '{"min_customers": 2}' },
  { value: "IP_SHARING", label: "IP Sharing", configHint: '{"min_customers": 3}' },
  { value: "LOCATION_CHANGE", label: "Location Change", configHint: "{}" },
  { value: "NEW_ACCOUNT_HIGH_VALUE", label: "New Account + High Value", configHint: '{"max_age_days": 7, "threshold": 500}' },
  { value: "UNUSUAL_TIME", label: "Unusual Activity Time", configHint: "{}" },
];

const emptyForm = {
  name: "",
  description: "",
  rule_type: RULE_TYPES[0].value,
  configuration: RULE_TYPES[0].configHint,
  risk_weight: 20,
};

export default function RulesPage() {
  const [rules, setRules] = useState<Rule[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [error, setError] = useState<string | null>(null);

  function load() {
    api.get("/rules").then((r) => setRules(r.data));
  }

  useEffect(load, []);

  function handleTypeChange(rule_type: string) {
    const hint = RULE_TYPES.find((t) => t.value === rule_type)?.configHint ?? "{}";
    setForm((f) => ({ ...f, rule_type, configuration: hint }));
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    let configuration: Record<string, unknown>;
    try {
      configuration = JSON.parse(form.configuration || "{}");
    } catch {
      setError("Configuration must be valid JSON, e.g. {\"threshold\": 5000}");
      return;
    }
    try {
      await api.post("/rules", {
        name: form.name,
        description: form.description || null,
        rule_type: form.rule_type,
        configuration,
        risk_weight: Number(form.risk_weight),
        is_active: true,
      });
      setForm(emptyForm);
      setShowForm(false);
      load();
    } catch {
      setError("Could not create rule. Check the fields and try again.");
    }
  }

  async function toggleActive(rule: Rule) {
    await api.put(`/rules/${rule.id}`, { is_active: !rule.is_active });
    load();
  }

  async function deleteRule(rule: Rule) {
    if (!confirm(`Delete rule "${rule.name}"? This cannot be undone.`)) return;
    await api.delete(`/rules/${rule.id}`);
    load();
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Fraud Rules Engine</h1>
        <button
          onClick={() => setShowForm((s) => !s)}
          className="bg-primary-600 text-white text-sm px-4 py-2 rounded-lg hover:bg-primary-700"
        >
          {showForm ? "Cancel" : "+ New Rule"}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="bg-white border border-primary-100/70 rounded-xl p-4 mb-6 space-y-3 dark:bg-[#141a2e] dark:border-white/10">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1 dark:text-slate-400">Rule Name</label>
              <input
                required
                className="w-full border border-slate-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/30 focus:border-primary-400 transition bg-white dark:bg-white/5 dark:border-white/10 dark:text-slate-100 dark:placeholder:text-slate-500"
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                placeholder="e.g. High amount threshold"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1 dark:text-slate-400">Rule Type</label>
              <select
                className="w-full border border-slate-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/30 focus:border-primary-400 transition bg-white dark:bg-white/5 dark:border-white/10 dark:text-slate-100 dark:placeholder:text-slate-500"
                value={form.rule_type}
                onChange={(e) => handleTypeChange(e.target.value)}
              >
                {RULE_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1 dark:text-slate-400">Description</label>
            <input
              className="w-full border border-slate-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/30 focus:border-primary-400 transition bg-white dark:bg-white/5 dark:border-white/10 dark:text-slate-100 dark:placeholder:text-slate-500"
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              placeholder="What this rule catches and why"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1 dark:text-slate-400">Configuration (JSON)</label>
              <input
                className="w-full border border-slate-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/30 focus:border-primary-400 transition font-mono bg-white dark:bg-white/5 dark:border-white/10 dark:text-slate-100 dark:placeholder:text-slate-500"
                value={form.configuration}
                onChange={(e) => setForm((f) => ({ ...f, configuration: e.target.value }))}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1 dark:text-slate-400">Risk Weight (0-100)</label>
              <input
                type="number"
                min={0}
                max={100}
                className="w-full border border-slate-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/30 focus:border-primary-400 transition bg-white dark:bg-white/5 dark:border-white/10 dark:text-slate-100 dark:placeholder:text-slate-500"
                value={form.risk_weight}
                onChange={(e) => setForm((f) => ({ ...f, risk_weight: Number(e.target.value) }))}
              />
            </div>
          </div>

          {error && <p className="text-red-600 text-sm dark:text-red-400">{error}</p>}

          <button className="bg-primary-600 text-white text-sm px-4 py-1.5 rounded-lg">Create Rule</button>
        </form>
      )}

      <div className="bg-white rounded-xl shadow-card border border-primary-100/70 overflow-hidden dark:bg-[#141a2e] dark:border-white/10 dark:shadow-none">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-500 text-left dark:bg-white/5 dark:text-slate-400">
            <tr>
              <th className="px-4 py-2">Name</th>
              <th className="px-4 py-2">Type</th>
              <th className="px-4 py-2">Configuration</th>
              <th className="px-4 py-2">Weight</th>
              <th className="px-4 py-2">Status</th>
              <th className="px-4 py-2"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-white/5">
            {rules.map((r) => (
              <tr key={r.id} className="hover:bg-slate-50 dark:hover:bg-white/5">
                <td className="px-4 py-2">
                  <div className="font-medium">{r.name}</div>
                  {r.description && <div className="text-xs text-slate-500 dark:text-slate-400">{r.description}</div>}
                </td>
                <td className="px-4 py-2 text-xs">{r.rule_type}</td>
                <td className="px-4 py-2 text-xs font-mono text-slate-600 dark:text-slate-400">{JSON.stringify(r.configuration)}</td>
                <td className="px-4 py-2">{r.risk_weight}</td>
                <td className="px-4 py-2">
                  <button
                    onClick={() => toggleActive(r)}
                    className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
                      r.is_active
                        ? "bg-green-100 text-green-800 dark:bg-green-500/10 dark:text-green-400"
                        : "bg-slate-200 text-slate-600 dark:bg-white/10 dark:text-slate-300"
                    }`}
                  >
                    {r.is_active ? "Active" : "Disabled"}
                  </button>
                </td>
                <td className="px-4 py-2 text-right">
                  <button onClick={() => deleteRule(r)} className="text-red-500 hover:text-red-700 text-xs dark:text-red-400 dark:hover:text-red-300">
                    Delete
                  </button>
                </td>
              </tr>
            ))}
            {rules.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-6 text-center text-slate-400 dark:text-slate-500">No rules configured yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
