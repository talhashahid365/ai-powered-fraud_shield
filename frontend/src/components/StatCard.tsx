interface Theme {
  bg: string;
  text: string;
  bar: string;
}

const PALETTE: Theme[] = [
  { bg: "bg-violet-50 dark:bg-violet-500/10", text: "text-violet-600 dark:text-violet-400", bar: "bg-violet-500" },
  { bg: "bg-emerald-50 dark:bg-emerald-500/10", text: "text-emerald-600 dark:text-emerald-400", bar: "bg-emerald-500" },
  { bg: "bg-amber-50 dark:bg-amber-500/10", text: "text-amber-600 dark:text-amber-400", bar: "bg-amber-500" },
  { bg: "bg-sky-50 dark:bg-sky-500/10", text: "text-sky-600 dark:text-sky-400", bar: "bg-sky-500" },
  { bg: "bg-pink-50 dark:bg-pink-500/10", text: "text-pink-600 dark:text-pink-400", bar: "bg-pink-500" },
];

const ICONS = [
  // shield / overview
  "M12 3l7 3v5c0 5-3.4 8.4-7 10-3.6-1.6-7-5-7-10V6l7-3z",
  // trending up
  "M3 17l6-6 4 4 8-8M21 7v6h-6",
  // alert triangle
  "M10.29 3.86l-8.18 14.02A2 2 0 004 21h16a2 2 0 001.89-3.12L13.71 3.86a2 2 0 00-3.42 0zM12 9v4m0 4h.01",
  // check circle
  "M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z",
  // gauge / score
  "M12 8v4l3 2M12 21a9 9 0 100-18 9 9 0 000 18z",
];

function themeForAccent(accent: string | undefined, index: number): { theme: Theme; icon: string } {
  if (accent?.includes("red"))
    return { theme: { bg: "bg-red-50 dark:bg-red-500/10", text: "text-red-600 dark:text-red-400", bar: "bg-red-500" }, icon: ICONS[2] };
  if (accent?.includes("amber"))
    return { theme: { bg: "bg-amber-50 dark:bg-amber-500/10", text: "text-amber-600 dark:text-amber-400", bar: "bg-amber-500" }, icon: ICONS[2] };
  if (accent?.includes("green") || accent?.includes("emerald"))
    return { theme: { bg: "bg-emerald-50 dark:bg-emerald-500/10", text: "text-emerald-600 dark:text-emerald-400", bar: "bg-emerald-500" }, icon: ICONS[3] };
  const theme = PALETTE[index % PALETTE.length];
  return { theme, icon: ICONS[index % ICONS.length] };
}

// Stable pseudo-random index derived from the label so the same stat always
// gets the same color/icon across renders, without needing a new prop.
function hashIndex(label: string) {
  let h = 0;
  for (let i = 0; i < label.length; i++) h = (h * 31 + label.charCodeAt(i)) % PALETTE.length;
  return Math.abs(h);
}

export default function StatCard({ label, value, accent }: { label: string; value: string | number; accent?: string }) {
  const { theme, icon } = themeForAccent(accent, hashIndex(label));
  // Value color always comes from `theme.text` (which carries a dark: variant),
  // never the raw `accent` string directly — a bare "text-red-600" with no dark
  // counterpart is what made these numbers vanish against the dark card background.
  const valueClass = accent ? theme.text : "text-slate-900 dark:text-slate-50";

  return (
    <div className="app-card hover:shadow-soft transition-shadow">
      <div className="flex items-center gap-3 mb-3">
        <div className={`w-10 h-10 rounded-full flex items-center justify-center ${theme.bg} ${theme.text}`}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d={icon} />
          </svg>
        </div>
        <div className="text-xs font-medium text-slate-500 dark:text-slate-400 leading-tight">{label}</div>
      </div>
      <div className={`text-2xl font-display font-bold ${valueClass}`}>{value}</div>
      <div className="mt-3 h-1.5 rounded-full bg-slate-100 dark:bg-white/10 overflow-hidden">
        <div className={`h-full w-2/3 rounded-full ${theme.bar}`} />
      </div>
    </div>
  );
}
