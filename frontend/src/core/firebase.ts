import { initializeApp, type FirebaseApp, type FirebaseOptions } from "firebase/app";

// Public Firebase Web config — these are identifiers, not secrets (the private
// FCM service-account key lives in the notifications service). Read from Vite
// env so a fork can point at its own project without code changes.
const config: FirebaseOptions = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

export const VAPID_KEY = import.meta.env.VITE_FIREBASE_VAPID_KEY ?? "";

/** True only when enough config is present to acquire an FCM token. */
export function firebaseConfigured(): boolean {
  return Boolean(config.apiKey && config.messagingSenderId && config.appId && VAPID_KEY);
}

let app: FirebaseApp | null = null;

export function getFirebaseApp(): FirebaseApp {
  if (!app) app = initializeApp(config);
  return app;
}
