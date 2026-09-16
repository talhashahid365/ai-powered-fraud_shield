interface LogoProps {
  /** Pixel size of the mark (square). Wordmark text scales with it. */
  size?: number;
  /** Show the "FraudShield" wordmark next to the mark. */
  withText?: boolean;
  /** Use light wordmark text for dark backgrounds. */
  light?: boolean;
  className?: string;
}

/**
 * Brand mark for FraudShield AI — a gradient rounded-square badge with a
 * shield + checkmark glyph. Used in the sidebar, login screen, and favicon.
 */
export default function Logo({ size = 36, withText = true, light = false, className = "" }: LogoProps) {
  return (
    <div className={`flex items-center gap-2.5 ${className}`}>
      <svg width={size} height={size} viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" className="shrink-0">
        <defs>
          <linearGradient id="fs-logo-gradient" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#8b78f4" />
            <stop offset="0.55" stopColor="#5b3ff0" />
            <stop offset="1" stopColor="#22d3ee" />
          </linearGradient>
        </defs>
        <rect width="64" height="64" rx="18" fill="url(#fs-logo-gradient)" />
        <path
          d="M32 10 L50 17 V30 C50 42 42.5 50.5 32 54 C21.5 50.5 14 42 14 30 V17 Z"
          fill="white"
          fillOpacity="0.95"
        />
        {/* Magnifying glass — fraud detection / investigation */}
        <circle cx="29" cy="27" r="8" stroke="#4b31d1" strokeWidth="4" fill="none" />
        <path d="M35 33 L41.5 39.5" stroke="#4b31d1" strokeWidth="4.5" strokeLinecap="round" />
        {/* Alert ping — active monitoring accent */}
        <circle cx="47" cy="15" r="6.5" fill="#ef4444" stroke="white" strokeWidth="2" />
      </svg>
      {withText && (
        <span className="font-display font-bold leading-none" style={{ fontSize: size * 0.5 }}>
          <span className={light ? "text-white" : "text-slate-900"}>Fraud</span>
          <span className={light ? "text-primary-200" : "text-primary-600"}>Shield</span>
        </span>
      )}
    </div>
  );
}
