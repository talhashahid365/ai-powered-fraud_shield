import React, { useMemo, useRef, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import type { UserRole } from "../types";
import NotificationBell from "../components/NotificationBell";
import ThemeToggle from "../components/ThemeToggle";
import Logo from "../components/Logo";

interface NavItem {
  to: string;
  label: string;
  icon: React.ReactNode;
  roles?: UserRole[]; // omit = visible to all roles
}

interface NavGroup {
  label: string | null; // null = ungrouped, rendered at the top with no heading
  items: NavItem[];
}

function NavIcon({ d }: { d: string }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d={d} />
    </svg>
  );
}

const NAV_GROUPS: NavGroup[] = [
  {
    label: null,
    items: [
      { to: "/dashboard", label: "Dashboard", icon: <NavIcon d="M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z" /> },
      { to: "/admin-dashboard", label: "Admin Dashboard", roles: ["ADMIN"], icon: <NavIcon d="M4 13h6V4H4v9zm0 7h6v-5H4v5zm10 0h6V11h-6v9zm0-16v5h6V4h-6z" /> },
    ],
  },
  {
    label: "Monitoring",
    items: [
      { to: "/transactions", label: "Transactions", icon: <NavIcon d="M3 10h18M7 15h1m4 0h5M5 6h14a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2z" /> },
      { to: "/alerts", label: "Alerts", icon: <NavIcon d="M12 9v4m0 4h.01M10.29 3.86l-8.18 14.02A2 2 0 004 21h16a2 2 0 001.89-3.12L13.71 3.86a2 2 0 00-3.42 0z" /> },
      { to: "/fraud-network", label: "Fraud Network", icon: <NavIcon d="M12 2a3 3 0 100 6 3 3 0 000-6zM4 20a3 3 0 100-6 3 3 0 000 6zm16 0a3 3 0 100-6 3 3 0 000 6zM7 16l4-8m2 8l4-8" /> },
    ],
  },
  {
    label: "Analytics",
    items: [
      { to: "/reports", label: "Reports", icon: <NavIcon d="M9 17V9m4 8V5m4 12v-6M5 21h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v14a2 2 0 002 2z" /> },
      { to: "/customers", label: "Customers", icon: <NavIcon d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2M9 11a4 4 0 100-8 4 4 0 000 8zm7 4a4 4 0 100-8 4 4 0 000 8z" /> },
    ],
  },
  {
    label: "Configuration",
    items: [
      { to: "/rules", label: "Rules Engine", roles: ["ADMIN"], icon: <NavIcon d="M4 6h16M4 12h16M4 18h7" /> },
      { to: "/api-keys", label: "API Keys", roles: ["ADMIN"], icon: <NavIcon d="M15 7a2 2 0 012 2m4 0a6 6 0 11-12 0 6 6 0 0112 0zM3 21l6.5-6.5" /> },
    ],
  },
  {
    label: "System",
    items: [{ to: "/audit-logs", label: "Audit Logs", roles: ["ADMIN"], icon: <NavIcon d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /> }],
  },
];

function initials(name?: string) {
  if (!name) return "?";
  return name
    .split(" ")
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

export default function AppLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate("/login");
  }

  const visibleGroups = NAV_GROUPS.map((group) => ({
    ...group,
    items: group.items.filter((item) => !item.roles || (user && item.roles.includes(user.role))),
  })).filter((group) => group.items.length > 0);

  // Flat list of every nav destination the current user can reach, used to
  // power the "Find something here..." search below.
  const searchableItems = useMemo(() => visibleGroups.flatMap((g) => g.items), [visibleGroups]);

  const [searchQuery, setSearchQuery] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);

  const searchMatches = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return [];
    return searchableItems.filter((item) => item.label.toLowerCase().includes(q));
  }, [searchQuery, searchableItems]);

  React.useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setSearchOpen(false);
      }
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  function goToSearchResult(to: string) {
    navigate(to);
    setSearchQuery("");
    setSearchOpen(false);
  }

  function handleSearchKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" && searchMatches.length > 0) {
      goToSearchResult(searchMatches[0].to);
    } else if (e.key === "Escape") {
      setSearchOpen(false);
    }
  }

  return (
    <div className="min-h-screen flex bg-[#f6f5fc] dark:bg-[#0b0e1c]">
      <aside className="w-64 bg-[#0d1225] flex flex-col shrink-0">
        <div className="px-5 py-6">
          <Logo size={38} light />
        </div>

        <nav className="flex-1 px-3 pb-4 space-y-5 overflow-y-auto">
          {visibleGroups.map((group, gi) => (
            <div key={group.label ?? `group-${gi}`}>
              {group.label && <div className="px-3.5 pb-2 text-[11px] font-bold tracking-widest text-slate-500 uppercase">{group.label}</div>}
              <div className="space-y-1">
                {group.items.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    className={({ isActive }) =>
                      `flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm font-medium transition-colors border-l-[3px] ${
                        isActive
                          ? "bg-primary-500/15 text-white border-primary-400"
                          : "text-slate-400 border-transparent hover:bg-white/5 hover:text-slate-100"
                      }`
                    }
                  >
                    {item.icon}
                    {item.label}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>

        <div className="mx-4 mb-5 mt-2 p-3.5 rounded-2xl bg-gradient-to-br from-primary-600 to-primary-800 text-white shadow-soft">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-full bg-white/20 flex items-center justify-center text-sm font-bold">
              {initials(user?.name)}
            </div>
            <div className="min-w-0">
              <div className="text-sm font-semibold truncate">{user?.name}</div>
              <div className="text-[11px] text-primary-100/90 truncate">{user?.role?.replace("_", " ")}</div>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="mt-3 w-full flex items-center justify-center gap-1.5 text-xs font-semibold bg-white text-primary-700 hover:bg-red-50 hover:text-red-600 transition-colors rounded-lg py-1.5 shadow-sm"
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4" />
              <path d="M16 17l5-5-5-5M21 12H9" />
            </svg>
            Log out
          </button>
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-16 shrink-0 flex items-center justify-between gap-4 px-6 bg-white/80 dark:bg-[#0f1428]/90 backdrop-blur border-b border-primary-100/60 dark:border-white/10">
          <div ref={searchRef} className="relative hidden sm:block w-full max-w-sm">
            <div className="flex items-center gap-2 bg-slate-100/80 dark:bg-white/5 rounded-xl px-3 py-2 text-slate-400 dark:text-slate-500 focus-within:ring-2 focus-within:ring-primary-300 dark:focus-within:ring-primary-500/40">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" className="shrink-0">
                <circle cx="11" cy="11" r="7" />
                <path d="M21 21l-4.35-4.35" />
              </svg>
              <input
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  setSearchOpen(true);
                }}
                onFocus={() => setSearchOpen(true)}
                onKeyDown={handleSearchKeyDown}
                placeholder="Find something here..."
                className="bg-transparent text-sm outline-none w-full text-slate-700 dark:text-slate-200 placeholder:text-slate-400 dark:placeholder:text-slate-500"
              />
            </div>
            {searchOpen && searchQuery.trim() && (
              <div className="absolute top-[calc(100%+6px)] left-0 right-0 bg-white dark:bg-[#141a2e] border border-primary-100/70 dark:border-white/10 rounded-xl shadow-soft overflow-hidden z-30 max-h-72 overflow-y-auto">
                {searchMatches.length > 0 ? (
                  searchMatches.map((item) => (
                    <button
                      key={item.to}
                      type="button"
                      onClick={() => goToSearchResult(item.to)}
                      className="w-full flex items-center justify-between gap-3 px-4 py-2.5 text-left text-sm text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-white/5 transition-colors"
                    >
                      <span className="flex items-center gap-2.5">
                        <span className="text-primary-500">{item.icon}</span>
                        {item.label}
                      </span>
                      <span className="text-slate-300 dark:text-slate-600 text-xs">Go to →</span>
                    </button>
                  ))
                ) : (
                  <p className="px-4 py-3 text-sm text-slate-400 text-center">No matches for "{searchQuery}"</p>
                )}
              </div>
            )}
          </div>
          <div className="flex items-center gap-3 ml-auto">
            <ThemeToggle />
            <NotificationBell />
            <div className="flex items-center gap-2.5">
              <div className="w-9 h-9 rounded-full bg-primary-100 text-primary-700 flex items-center justify-center text-xs font-bold shrink-0">
                {initials(user?.name)}
              </div>
              <div className="hidden md:block leading-tight">
                <div className="text-sm font-semibold text-slate-800 dark:text-slate-100">{user?.name}</div>
                <div className="text-[11px] text-slate-400 dark:text-slate-500">{user?.role?.replace("_", " ")}</div>
              </div>
            </div>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto">
          <div className="p-6 max-w-7xl mx-auto">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
