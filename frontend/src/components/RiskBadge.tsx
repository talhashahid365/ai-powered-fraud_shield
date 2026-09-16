const COLORS: Record<string, { pill: string; dot: string }> = {
  LOW: { pill: "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400", dot: "bg-emerald-500" },
  MEDIUM: { pill: "bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-400", dot: "bg-amber-500" },
  HIGH: { pill: "bg-red-50 text-red-700 dark:bg-red-500/10 dark:text-red-400", dot: "bg-red-500" },
  CRITICAL: { pill: "bg-red-100 text-red-800 dark:bg-red-500/20 dark:text-red-300", dot: "bg-red-700" },
};

export default function RiskBadge({ level }: { level: string }) {
  const theme = COLORS[level] || { pill: "bg-slate-100 text-slate-700 dark:bg-white/10 dark:text-slate-300", dot: "bg-slate-400" };
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${theme.pill}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${theme.dot}`} />
      {level}
    </span>
  );
}
