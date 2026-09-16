import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import Logo from "../components/Logo";

function EyeIcon({ off }: { off: boolean }) {
  return off ? (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17.94 17.94A10.94 10.94 0 0112 20c-6 0-9.27-5.44-10.5-8 .58-1.2 1.6-2.86 3.06-4.34M9.9 4.24A10.9 10.9 0 0112 4c6 0 9.27 5.44 10.5 8-.42.87-1.06 1.98-1.93 3.11M14.12 14.12a3 3 0 11-4.24-4.24" />
      <path d="M1 1l22 22" />
    </svg>
  ) : (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M1.5 12S5 5 12 5s10.5 7 10.5 7-3.5 7-10.5 7S1.5 12 1.5 12z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function MailIcon() {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="M3 7l9 6 9-6" />
    </svg>
  );
}

function LockIcon() {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <rect x="5" y="10" width="14" height="10" rx="2" />
      <path d="M8 10V7a4 4 0 018 0v3" />
    </svg>
  );
}

/** Decorative wireframe shield + checkmark, matching the marketing background. */
function ShieldGlyph() {
  return (
    <svg
      viewBox="0 0 400 400"
      className="absolute right-[-40px] top-1/2 -translate-y-1/2 w-[320px] h-[320px] sm:w-[420px] sm:h-[420px] pointer-events-none select-none opacity-90"
      aria-hidden="true"
    >
      <defs>
        <linearGradient id="shield-glyph-grad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#8b78f4" />
          <stop offset="100%" stopColor="#67e8f9" />
        </linearGradient>
        <radialGradient id="shield-glow" cx="50%" cy="45%" r="55%">
          <stop offset="0%" stopColor="#6d56ef" stopOpacity="0.35" />
          <stop offset="100%" stopColor="#6d56ef" stopOpacity="0" />
        </radialGradient>
      </defs>
      <circle cx="200" cy="190" r="170" fill="url(#shield-glow)" />
      {/* constellation dots */}
      {[
        [80, 90], [320, 110], [60, 260], [330, 250], [200, 40], [110, 330], [290, 330],
      ].map(([cx, cy], i) => (
        <circle key={i} cx={cx} cy={cy} r="2.5" fill="#8fd9ff" opacity="0.7" />
      ))}
      <g opacity="0.35" stroke="#8b78f4" strokeWidth="1">
        <line x1="80" y1="90" x2="200" y2="60" />
        <line x1="320" y1="110" x2="200" y2="60" />
        <line x1="60" y1="260" x2="110" y2="330" />
        <line x1="330" y1="250" x2="290" y2="330" />
      </g>
      <path
        d="M200 60 L300 100 V190 C300 260 258 310 200 335 C142 310 100 260 100 190 V100 Z"
        fill="none"
        stroke="url(#shield-glyph-grad)"
        strokeWidth="4"
        strokeLinejoin="round"
        opacity="0.85"
      />
      <path
        d="M160 195 L188 223 L245 160"
        fill="none"
        stroke="url(#shield-glyph-grad)"
        strokeWidth="9"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

const FEATURES = [
  {
    label: "Real-time\nMonitoring",
    icon: (
      <svg width="19" height="19" viewBox="0 0 24 24" fill="#c7b6ff">
        <path d="M13 2L4 14h7l-1 8 9-12h-7l1-8z" />
      </svg>
    ),
  },
  {
    label: "Smarter\nInvestigations",
    icon: (
      <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="#9fd0ff" strokeWidth="1.8">
        <path d="M12 3l7 3v6c0 4.5-3 8-7 9-4-1-7-4.5-7-9V6l7-3z" />
        <path d="M9 12l2 2 4-4" />
      </svg>
    ),
  },
  {
    label: "Safer\nTransactions",
    icon: (
      <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="#c7b6ff" strokeWidth="2.2" strokeLinecap="round">
        <path d="M4 20V10M11 20V4M18 20v-7" />
      </svg>
    ),
  },
];

export default function LoginPage() {
  const { login, isLoading } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("admin@fraudshield.ai");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await login(email, password);
      navigate("/dashboard");
    } catch {
      setError("Invalid email or password.");
    }
  }

  return (
    <div className="login-shell min-h-screen flex items-center justify-center px-6 md:px-16 py-14">
      <div className="w-full max-w-6xl grid md:grid-cols-2 gap-16 items-center relative z-10">
        {/* Left — hero copy */}
        <div className="relative">
          <div className="mb-14">
            <Logo size={40} light />
          </div>

          <ShieldGlyph />

          <h1 className="font-display text-4xl sm:text-5xl font-extrabold leading-[1.08] tracking-tight text-white mb-6 relative z-10">
            AI-powered fraud
            <br />
            detection,
            <br />
            <span className="bg-gradient-to-r from-primary-400 to-cyan-300 bg-clip-text text-transparent">
              in real time.
            </span>
          </h1>
          <p className="text-slate-400 text-base leading-relaxed max-w-md mb-11 relative z-10">
            Monitor transactions, investigate alerts, and stop fraud rings before they cost you —
            all from one dashboard.
          </p>

          <div className="flex flex-wrap gap-8 relative z-10">
            {FEATURES.map((f) => (
              <div key={f.label} className="flex items-center gap-3">
                <div className="login-feature-icon">{f.icon}</div>
                <span className="text-slate-200 text-sm font-semibold leading-snug whitespace-pre-line">
                  {f.label}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Right — sign-in card */}
        <div className="flex md:justify-end">
          <form onSubmit={handleSubmit} className="login-card w-full max-w-md rounded-3xl p-9 sm:p-11">
            <h1 className="font-display text-3xl font-extrabold mb-2 text-white">Welcome Back</h1>
            <p className="text-slate-400 text-sm mb-8">Sign in to the fraud &amp; risk detection platform</p>

            <label className="block text-sm font-semibold mb-2 text-slate-200">Email</label>
            <div className="relative mb-5">
              <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500">
                <MailIcon />
              </span>
              <input
                className="login-field"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                type="email"
                required
              />
            </div>

            <label className="block text-sm font-semibold mb-2 text-slate-200">Password</label>
            <div className="relative mb-5">
              <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500">
                <LockIcon />
              </span>
              <input
                className="login-field pr-11"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                type={showPassword ? "text" : "password"}
                placeholder="Enter your password"
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword((s) => !s)}
                className="absolute right-0 top-0 h-full px-3.5 flex items-center text-slate-500 hover:text-slate-300 transition-colors"
                aria-label={showPassword ? "Hide password" : "Show password"}
                tabIndex={-1}
              >
                <EyeIcon off={showPassword} />
              </button>
            </div>

            {error && <p className="text-red-400 text-sm mb-3">{error}</p>}

            <button
              type="submit"
              disabled={isLoading}
              className="login-submit w-full py-3.5 text-[15px] font-bold text-white rounded-xl disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {isLoading ? "Signing in..." : "Sign In"}
              {!isLoading && (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M5 12h14M13 6l6 6-6 6" />
                </svg>
              )}
            </button>
          </form>
        </div>
      </div>

      <p className="absolute left-6 md:left-16 bottom-8 text-slate-500 text-xs z-10">
        © {new Date().getFullYear()} FraudShield AI
      </p>
    </div>
  );
}
