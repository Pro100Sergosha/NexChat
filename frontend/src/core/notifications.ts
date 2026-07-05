import { apiFetch } from "./api";
import type { DevicePlatform, DeviceToken, NotificationItem } from "./types";

export const API_NOTIF = "/api/notifications";

/** The caller's notification history, newest first. */
export function listNotifications(): Promise<NotificationItem[]> {
  return apiFetch<NotificationItem[]>(`${API_NOTIF}/notifications`);
}

/** Mark one of the caller's own notifications read → 204. */
export function markRead(id: string): Promise<void> {
  return apiFetch<void>(`${API_NOTIF}/notifications/${id}/read`, { method: "POST" });
}

/** Register an FCM device token for offline push → 201. */
export function registerDevice(
  token: string,
  platform: DevicePlatform,
): Promise<DeviceToken> {
  return apiFetch<DeviceToken>(`${API_NOTIF}/devices`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, platform }),
  });
}

/** Drop a previously-registered device token → 204. */
export function unregisterDevice(token: string): Promise<void> {
  return apiFetch<void>(`${API_NOTIF}/devices/${encodeURIComponent(token)}`, {
    method: "DELETE",
  });
}

/**
 * SSE endpoint URL. EventSource can't set an Authorization header, so the
 * access token rides the query string (same as chat's WS handshake); a bad
 * token is a plain 401 and the stream reconnects after a refresh.
 */
export function eventsUrl(token: string): string {
  return `${API_NOTIF}/events?token=${encodeURIComponent(token)}`;
}
