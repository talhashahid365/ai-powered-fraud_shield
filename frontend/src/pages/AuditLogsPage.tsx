import { useEffect, useState } from "react";
import { api } from "../services/api";
import type { AuditLogEntry } from "../types";

export default function AuditLogsPage() {
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);

  useEffect(() => {
    api.get("/audit-logs", { params: { limit: 200 } }).then((r) => setLogs(r.data));
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Audit Logs</h1>
      <div className="bg-white rounded-xl shadow-card border border-primary-100/70 overflow-hidden dark:bg-[#141a2e] dark:border-white/10 dark:shadow-none">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-500 text-left dark:bg-white/5 dark:text-slate-400">
            <tr>
              <th className="px-4 py-2">Action</th>
              <th className="px-4 py-2">Details</th>
              <th className="px-4 py-2">IP</th>
              <th className="px-4 py-2">When</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-white/5">
            {logs.map((l) => (
              <tr key={l.id} className="hover:bg-slate-50 dark:hover:bg-white/5">
                <td className="px-4 py-2 font-medium">{l.action}</td>
                <td className="px-4 py-2 text-slate-600 dark:text-slate-300">{l.details}</td>
                <td className="px-4 py-2 text-slate-500 dark:text-slate-400">{l.ip_address ?? "—"}</td>
                <td className="px-4 py-2 text-slate-500 dark:text-slate-400">{new Date(l.created_at).toLocaleString()}</td>
              </tr>
            ))}
            {logs.length === 0 && (
              <tr><td colSpan={4} className="px-4 py-6 text-center text-slate-400 dark:text-slate-500">No audit events yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
