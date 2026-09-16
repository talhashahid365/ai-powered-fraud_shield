import Sparkline from "./Sparkline";

export type StatColor = "blue" | "red" | "amber" | "pink" | "violet" | "teal" | "emerald" | "indigo" | "slate";

// Full literal class names (never interpolated) so Tailwind's scanner can see
// and generate every one of these utilities at build time.
const THEME: Record<StatColor, { bg: string; text: string; spark: string; bar: string }> = {
  blue: { bg: "bg-blue-50 dark:bg-blue-500/10", text: "text-blue-600 dark:text-blue-400", spark: "#2563eb", bar: "bg-blue-500" },
  red: { bg: "bg-red-50 dark:bg-red-500/10", text: "text-red-600 dark:text-red-400", spark: "#dc2626", bar: "bg-red-500" },
  amber: { bg: "bg-amber-50 dark:bg-amber-500/10", text: "text-amber-600 dark:text-amber-400", spark: "#d97706", bar: "bg-amber-500" },
  pink: { bg: "bg-pink-50 dark:bg-pink-500/10", text: "text-pink-600 dark:text-pink-400", spark: "#db2777", bar: "bg-pink-500" },
  violet: { bg: "bg-violet-50 dark:bg-violet-500/10", text: "text-violet-600 dark:text-violet-400", spark: "#7c3aed", bar: "bg-violet-500" },
  teal: { bg: "bg-teal-50 dark:bg-teal-500/10", text: "text-teal-600 dark:text-teal-400", spark: "#0d9488", bar: "bg-teal-500" },
  emerald: { bg: "bg-emerald-50 dark:bg-emerald-500/10", text: "text-emerald-600 dark:text-emerald-400", spark: "#059669", bar: "bg-emerald-500" },
  indigo: { bg: "bg-indigo-50 dark:bg-indigo-500/10", text: "text-indigo-600 dark:text-indigo-400", spark: "#4f46e5", bar: "bg-indigo-500" },
  slate: { bg: "bg-slate-100 dark:bg-white/10", text: "text-slate-600 dark:text-slate-300", spark: "#64748b", bar: "bg-slate-400" },
};

interface Props {
  label: string;
  value: string | number;
  icon: string;
  color: StatColor;
  /** Daily series for the mini chart. Shown instead of the plain bar when it has real movement. */
  sparklineData?: number[];
  /** % change vs. the earlier half of the selected range, when it can be honestly computed. */
  deltaPercent?: number;
  /** Decorative fallback width (0-100) for stats with no time series to chart. */
  barPercent?: number;
  /** Fades the card when the active header filters (risk/status) don't apply to it. */
  dim?: boolean;
}

export default function DashboardStatCard({
  label,
  value,
  icon,
  color,
  sparklineData,
  deltaPercent,
  barPercent = 55,
  dim = false,
}: Props) {
  const theme = THEME[color];
  const hasSpark = !!sparklineData && sparklineData.length >= 2 && sparklineData.some((v) => v !== sparklineData[0]);

  return (
    <div className={`app-card !p-5 flex flex-col transition-opacity duration-150 ${dim ? "opacity-40 scale-[0.98]" : "opacity-100"}`}>
      <div className="flex items-center justify-between mb-4">
        <div className={`w-11 h-11 rounded-xl flex items-center justify-center ${theme.bg} ${theme.text}`}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d={icon} />
          </svg>
        </div>
        {deltaPercent !== undefined && Number.isFinite(deltaPercent) && (
          <span className={`inline-flex items-center gap-1 text-xs font-semibold ${deltaPercent >= 0 ? "text-emerald-600" : "text-red-500"}`}>
            <svg
              width="12"
              height="12"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="3"
              strokeLinecap="round"
              strokeLinejoin="round"
              className={deltaPercent < 0 ? "rotate-180" : ""}
            >
              <path d="M12 19V5M5 12l7-7 7 7" />
            </svg>
            {Math.abs(deltaPercent).toFixed(1)}%
          </span>
        )}
      </div>
      <div className="text-xs font-medium text-slate-500 dark:text-slate-400 mb-1 leading-tight">{label}</div>
      <div className="text-2xl font-display font-bold text-slate-900 dark:text-slate-50 mb-3">{value}</div>
      <div className="mt-auto -mx-1">
        {hasSpark ? (
          <Sparkline data={sparklineData!} color={theme.spark} />
        ) : (
          <div className="h-1.5 rounded-full bg-slate-100 dark:bg-white/10 overflow-hidden mx-1">
            <div className={`h-full rounded-full ${theme.bar}`} style={{ width: `${barPercent}%` }} />
          </div>
        )}
      </div>
    </div>
  );
}
