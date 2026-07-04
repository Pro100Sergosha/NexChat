// Thin wrapper over the browser Notification API for OS-level message alerts.

export function notifySupported(): boolean {
  return typeof window !== "undefined" && "Notification" in window;
}

export function notifyPermission(): NotificationPermission {
  return notifySupported() ? Notification.permission : "denied";
}

/** Ask for permission if not decided yet; returns whether we can notify. */
export async function requestNotifyPermission(): Promise<boolean> {
  if (!notifySupported()) return false;
  if (Notification.permission === "granted") return true;
  if (Notification.permission === "denied") return false;
  const result = await Notification.requestPermission();
  return result === "granted";
}

/** Show a notification (no-op unless permission was granted). */
export function showNotification(title: string, body: string): void {
  if (!notifySupported() || Notification.permission !== "granted") return;
  try {
    // Same tag => a burst of messages collapses instead of stacking.
    const n = new Notification(title, { body, tag: "nexchat-message" });
    n.onclick = () => {
      window.focus();
      n.close();
    };
  } catch {
    // Some engines only allow notifications from a service worker — ignore.
  }
}
