import { deleteToken, getMessaging, getToken, isSupported } from "firebase/messaging";
import { firebaseConfigured, getFirebaseApp, VAPID_KEY } from "./firebase";
import { registerDevice, unregisterDevice } from "./notifications";

// The FCM background handler must be a static file at the origin root.
const SW_URL = "/firebase-messaging-sw.js";
// Remember the last token we registered so we don't re-POST it every mount.
const TOKEN_KEY = "nexchat.fcm_token";

async function messagingOrNull(): Promise<ReturnType<typeof getMessaging> | null> {
  if (!firebaseConfigured()) return null;
  try {
    if (!(await isSupported())) return null;
    return getMessaging(getFirebaseApp());
  } catch {
    return null;
  }
}

/**
 * Register this browser for offline push. Best-effort and idempotent: a no-op
 * when Firebase isn't configured, the browser lacks push support, or the user
 * hasn't granted notification permission (the caller owns the prompt). FCM
 * only fires when the user has no live SSE socket, so this never double-delivers
 * with the in-app stream.
 */
export async function enablePush(): Promise<void> {
  try {
    if (Notification.permission !== "granted") return;
    const messaging = await messagingOrNull();
    if (!messaging) return;

    const registration = await navigator.serviceWorker.register(SW_URL);
    const token = await getToken(messaging, {
      vapidKey: VAPID_KEY,
      serviceWorkerRegistration: registration,
    });
    if (!token || localStorage.getItem(TOKEN_KEY) === token) return;

    await registerDevice(token, "web");
    localStorage.setItem(TOKEN_KEY, token);
  } catch {
    /* push is a best-effort enhancement over SSE — never surface a failure */
  }
}

/** Drop this browser's push registration (call on sign-out, tokens still valid). */
export async function disablePush(): Promise<void> {
  const token = localStorage.getItem(TOKEN_KEY);
  localStorage.removeItem(TOKEN_KEY);
  try {
    if (token) await unregisterDevice(token);
    const messaging = await messagingOrNull();
    if (messaging) await deleteToken(messaging);
  } catch {
    /* best-effort */
  }
}
