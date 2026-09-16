import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";
import type { RiskDistributionItem } from "../types";

const COLORS: Record<string, string> = { LOW: "#10b981", MEDIUM: "#f59e0b", HIGH: "#ef4444" };
const LABELS: Record<string, string> = { LOW: "Low Risk", MEDIUM: "Medium Risk", HIGH: "High Risk" };

export default function RiskDonut({ data }: { data: RiskDistributionItem[] }) {
  const total = data.reduce((sum, d) => sum + d.count, 0);

  return (
    // Always stacked: this card sits in a narrow grid column (~1/3 of the main
    // content area), so a viewport-based "sm:flex-row" used to kick in a
    // side-by-side layout the column itself was too narrow for — the donut +
    // legend row overflowed the card and bled into the System Health panel
    // next to it. Stacking removes that failure mode regardless of column width.
    <div className="flex flex-col items-center gap-5 min-w-0">
      <div className="relative w-[150px] h-[150px] shrink-0">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={data} dataKey="count" nameKey="risk_level" innerRadius={50} outerRadius={72} paddingAngle={total > 0 ? 3 : 0} stroke="none">
              {data.map((d) => (
                <Cell key={d.risk_level} fill={COLORS[d.risk_level] ?? "#cbd5e1"} />
              ))}
              {data.length === 0 && <Cell fill="#f1f5f9" />}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          <div className="text-2xl font-display font-bold text-slate-900 dark:text-slate-50">{total}</div>
          <div className="text-[11px] text-slate-400 dark:text-slate-500">Total</div>
        </div>
      </div>

      <div className="w-full min-w-0 space-y-2.5">
        {data.map((d) => (
          <div key={d.risk_level} className="flex items-center justify-between gap-2 text-sm">
            <span className="flex items-center gap-2 min-w-0 text-slate-600 dark:text-slate-300">
              <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: COLORS[d.risk_level] ?? "#94a3b8" }} />
              <span className="truncate">{LABELS[d.risk_level] ?? d.risk_level}</span>
            </span>
            <span className="shrink-0 font-semibold text-slate-800 dark:text-slate-100">
              {d.count} <span className="text-xs text-slate-400 dark:text-slate-500 font-normal">({total ? ((d.count / total) * 100).toFixed(1) : 0}%)</span>
            </span>
          </div>
        ))}
        {data.length === 0 && <div className="text-sm text-slate-400">No data in this range.</div>}
      </div>
    </div>
  );
}
