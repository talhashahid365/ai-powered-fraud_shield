import { useEffect, useRef } from "react";

export interface LiveTransactionEvent {
  type: "transaction.scored";
  transaction: {
    id: string;
    transaction_id: string;
    customer_id: string | null;
    amount: number;
    currency: string;
    risk_score: number;
    risk_level: string;
    decision: string;
    created_at: string | null;
  };
}

/**
 * Subscribes to the backend's real-time detection feed (see
 * backend/app/api/routes/ws.py). Every transaction that finishes the
 * Validation -> Rules -> ML -> Customer History -> Risk Engine -> Decision
 * pipeline is pushed here the moment it's scored, so callers (e.g. the
 * dashboard) can react without polling.
 *
 * Auto-reconnects with a fixed backoff if the connection drops (e.g. the
 * backend restarts), and cleans up on unmount.
 */
export function useLiveFeed(onEvent: (event: LiveTransactionEvent) => void) {
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  useEffect(() => {
    const token = localStorage.getItem("fraudshield_token");
    if (!token) return;

    let socket: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let cancelled = false;

    function connect() {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      socket = new WebSocket(`${protocol}//${window.location.host}/ws/live?token=${encodeURIComponent(token!)}`);

      socket.onmessage = (msg) => {
        try {
          const data = JSON.parse(msg.data) as LiveTransactionEvent;
          if (data?.type === "transaction.scored") {
            onEventRef.current(data);
          }
        } catch {
          // Ignore malformed frames rather than crashing the live feed.
        }
      };

      socket.onclose = () => {
        if (!cancelled) {
          reconnectTimer = setTimeout(connect, 4000);
        }
      };

      socket.onerror = () => {
        socket?.close();
      };
    }

    connect();

    return () => {
      cancelled = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, []);
}
