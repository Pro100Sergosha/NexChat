import { useCallback, useEffect, useRef, useState } from "react";
import { useAlerts } from "@/alerts/AlertsContext";
import { listNotifications, markRead as apiMarkRead } from "@/core/notifications";
import { NotifStream, type StreamStatus } from "@/core/notifStream";
import type { NotificationItem } from "@/core/types";

interface NotificationsState {
  items: NotificationItem[];
  status: StreamStatus;
  unread: number;
  markRead: (id: string) => void;
}

/**
 * Loads the caller's notification history once, then keeps a live SSE stream
 * open for the component's lifetime — new events prepend and raise an alert.
 * Meant to mount at a persistent point in the authed shell (the top bar).
 */
export function useNotifications(): NotificationsState {
  const alerts = useAlerts();
  const alertsRef = useRef(alerts);
  alertsRef.current = alerts;

  const [items, setItems] = useState<NotificationItem[]>([]);
  const [status, setStatus] = useState<StreamStatus>("connecting");

  useEffect(() => {
    let alive = true;
    void listNotifications()
      .then((list) => {
        if (alive) setItems(list);
      })
      .catch(() => {
        /* history is best-effort; the stream still delivers live events */
      });

    const stream = new NotifStream({
      onNotification: (n) => {
        setItems((prev) => (prev.some((p) => p.id === n.id) ? prev : [n, ...prev]));
        alertsRef.current.fire({
          title: n.title,
          body: n.body,
          desktop: document.hidden,
        });
      },
      onStatus: setStatus,
    });
    stream.connect();

    return () => {
      alive = false;
      stream.close();
    };
  }, []);

  const markRead = useCallback((id: string) => {
    // Optimistic — the row reads as seen immediately; the POST is best-effort.
    setItems((prev) => prev.map((n) => (n.id === id ? { ...n, read: true } : n)));
    void apiMarkRead(id).catch(() => {});
  }, []);

  const unread = items.reduce((count, n) => count + (n.read ? 0 : 1), 0);

  return { items, status, unread, markRead };
}
