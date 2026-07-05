import { useEffect, useRef, useState } from "react";
import { useNotifications } from "@/hooks/useNotifications";
import { railTime } from "@/core/format";
import styles from "./NotificationsBell.module.css";

/** Top-bar inbox: an unread badge + a dropdown of the notification history. */
export function NotificationsBell() {
  const { items, unread, markRead } = useNotifications();
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  // Close on outside click / Esc, like a typical menu.
  useEffect(() => {
    if (!open) return;
    const onDown = (e: PointerEvent) => {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("pointerdown", onDown);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("pointerdown", onDown);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className={styles.wrap} ref={wrapRef}>
      <button
        className={styles.bell}
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-label={unread > 0 ? `Notifications, ${unread} unread` : "Notifications"}
        aria-expanded={open}
      >
        <span aria-hidden>◔</span>
        {unread > 0 && (
          <span className={styles.badge}>{unread > 9 ? "9+" : unread}</span>
        )}
      </button>

      {open && (
        <div className={styles.panel} role="menu">
          <header className={styles.panelHead}>
            <span className="op-label">Notifications</span>
          </header>

          {items.length === 0 ? (
            <p className={styles.empty}>Nothing on the wire yet.</p>
          ) : (
            <ul className={styles.list}>
              {items.map((n) => (
                <li key={n.id}>
                  <button
                    className={n.read ? styles.item : styles.itemUnread}
                    type="button"
                    onClick={() => !n.read && markRead(n.id)}
                  >
                    <span className={styles.itemTop}>
                      <span className={styles.itemTitle}>{n.title}</span>
                      <time className={styles.itemTime}>{railTime(n.created_at)}</time>
                    </span>
                    <span className={styles.itemBody}>{n.body}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
