import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../services/api";
import type { Notification } from "../types";

// Fraud Alerts spec: "Notify the relevant user". Alerts are auto-assigned to an
// analyst on creation (backend: alert_service.create_alert_for_transaction), and a
// Notification row is created for that analyst. This polls for those notifications
// and surfaces them as a bell/dropdown - the "notify" half of the requirement,
// alongside the existing "show alert on dashboard" (DashboardPage) and "store the
// reason" / "assign severity" (Alert model, already covered).
export default function NotificationBell() {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  function load() {
    api.get("/notifications", { params: { limit: 15 } }).then((r) => {
      setNotifications(r.data.data);
      setUnreadCount(r.data.unread_count);
    });
  }

  useEffect(() => {
    load();
    const interval = setInterval(load, 30000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  async function handleOpen() {
    setOpen((o) => !o);
    if (!open && unreadCount > 0) {
      await api.post("/notifications/read", {});
      setUnreadCount(0);
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
    }
  }

  return (
    <div className="relative" ref={ref}>
      <button onClick={handleOpen} className="icon-btn" aria-label="Notifications">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M18 8a6 6 0 10-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.73 21a2 2 0 01-3.46 0" />
        </svg>
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 bg-red-500 text-white text-[10px] leading-none rounded-full min-w-[16px] h-4 px-1 flex items-center justify-center border-2 border-white">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 top-12 w-80 bg-white dark:bg-[#141a2e] border border-primary-100 dark:border-white/10 rounded-2xl shadow-soft z-50 max-h-96 overflow-y-auto">
          <div className="px-4 py-3 border-b border-slate-100 dark:border-white/10 text-sm font-semibold text-slate-700 dark:text-slate-200">
            Notifications
          </div>
          {notifications.length === 0 && (
            <div className="px-4 py-6 text-sm text-slate-400 text-center">No notifications yet.</div>
          )}
          {notifications.map((n) => (
            <button
              key={n.id}
              onClick={() => {
                setOpen(false);
                navigate("/alerts");
              }}
              className={`w-full text-left px-4 py-2.5 text-sm border-b border-slate-50 dark:border-white/5 hover:bg-primary-50/50 dark:hover:bg-white/5 ${
                n.is_read ? "text-slate-500" : "text-slate-900 dark:text-slate-100 font-medium"
              }`}
            >
              <div>{n.message}</div>
              <div className="text-xs text-slate-400 mt-0.5">{new Date(n.created_at).toLocaleString()}</div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
