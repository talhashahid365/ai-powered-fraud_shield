export interface FraudRingHubEntity {
  label: string;
  count: number;
}

const ENTITY_ICON_PATHS: Record<string, string> = {
  Users: "M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2M9 11a4 4 0 100-8 4 4 0 000 8zm7 4a4 4 0 100-8 4 4 0 000 8z",
  Devices: "M4 4h16a1 1 0 011 1v10a1 1 0 01-1 1H4a1 1 0 01-1-1V5a1 1 0 011-1zm5 16h6",
  "IP Addresses": "M12 2a10 10 0 100 20 10 10 0 000-20zm0 0c2.5 2.6 4 6.1 4 10s-1.5 7.4-4 10c-2.5-2.6-4-6.1-4-10s1.5-7.4 4-10zM2.5 9h19M2.5 15h19",
  Locations: "M12 22s7.5-7.6 7.5-13A7.5 7.5 0 104.5 9c0 5.4 7.5 13 7.5 13zm0-9.5a3.5 3.5 0 100-7 3.5 3.5 0 000 7z",
  Transactions: "M3 10h18M7 15h1m4 0h5M5 6h14a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2z",
};

const ENTITY_COLORS: Record<string, string> = {
  Users: "#8b5cf6",
  Devices: "#2563eb",
  "IP Addresses": "#059669",
  Locations: "#ea580c",
  Transactions: "#0d9488",
};

const SHIELD_PATH = "M12 2 19 5 V11 C19 16 15.5 19.5 12 21 C8.5 19.5 5 16 5 11 V5 Z";

/**
 * Static "hub & spoke" fraud-ring visual — a central ring node connected to
 * its related entities (users, devices, IPs, locations, transactions).
 * Renders reliably regardless of container sizing/measurement, unlike the
 * force-directed graph, and mirrors the reference concept illustration.
 */
export default function FraudRingHub({
  entities,
  height = 220,
  ringLabel = "Fraud Ring",
}: {
  entities: FraudRingHubEntity[];
  height?: number;
  ringLabel?: string;
}) {
  const cx = 110;
  const cy = 108;
  const radius = 78;
  const angleStep = entities.length > 0 ? (2 * Math.PI) / entities.length : 0;

  return (
    <div
      className="border border-slate-100 dark:border-white/10 rounded-lg overflow-hidden bg-slate-50/70 dark:bg-white/[0.03] flex items-center justify-center"
      style={{ height }}
    >
      <svg viewBox="0 0 220 216" className="w-full h-full max-w-[320px]">
        {entities.map((e, i) => {
          const angle = -Math.PI / 2 + i * angleStep;
          const x = cx + radius * Math.cos(angle);
          const y = cy + radius * Math.sin(angle);
          return (
            <line
              key={`line-${e.label}`}
              x1={cx}
              y1={cy}
              x2={x}
              y2={y}
              className="stroke-slate-300 dark:stroke-white/15"
              strokeWidth={1.5}
              strokeDasharray="3 4"
            />
          );
        })}

        {entities.map((e, i) => {
          const angle = -Math.PI / 2 + i * angleStep;
          const x = cx + radius * Math.cos(angle);
          const y = cy + radius * Math.sin(angle);
          const color = ENTITY_COLORS[e.label] ?? "#64748b";
          const iconPath = ENTITY_ICON_PATHS[e.label] ?? ENTITY_ICON_PATHS.Users;
          return (
            <g key={e.label}>
              <circle cx={x} cy={y} r={18} fill={color} />
              <svg x={x - 8} y={y - 8} width={16} height={16} viewBox="0 0 24 24">
                <path d={iconPath} fill="none" stroke="white" strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              <circle cx={x + 13} cy={y - 13} r={9} className="fill-white dark:fill-[#141a2e]" stroke={color} strokeWidth={1.4} />
              <text x={x + 13} y={y - 10} textAnchor="middle" fontSize={8.5} fontWeight={700} className="fill-slate-700 dark:fill-slate-100">
                {e.count}
              </text>
              <text x={x} y={y + 30} textAnchor="middle" fontSize={9.5} fontWeight={600} className="fill-slate-500 dark:fill-slate-400">
                {e.label}
              </text>
            </g>
          );
        })}

        <circle cx={cx} cy={cy} r={27} fill="#dc2626" />
        <circle cx={cx} cy={cy} r={27} fill="none" stroke="#dc2626" strokeOpacity={0.35} strokeWidth={5} />
        <svg x={cx - 11} y={cy - 11} width={22} height={22} viewBox="0 0 24 24">
          <path d={SHIELD_PATH} fill="none" stroke="white" strokeWidth={2.2} strokeLinejoin="round" />
          <path d="M9 12l2 2 4-4" stroke="white" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" fill="none" />
        </svg>
        <text x={cx} y={cy + 44} textAnchor="middle" fontSize={10.5} fontWeight={700} className="fill-slate-700 dark:fill-slate-100">
          {ringLabel}
        </text>
      </svg>
    </div>
  );
}
