/* FCM background message handler. Served static at the origin root; a service
 * worker can't read Vite's import.meta.env, so the (public, non-secret) Firebase
 * Web config is inlined here. Keep it in sync with frontend/.env.example. */
importScripts(
  "https://www.gstatic.com/firebasejs/12.15.0/firebase-app-compat.js",
);
importScripts(
  "https://www.gstatic.com/firebasejs/12.15.0/firebase-messaging-compat.js",
);

firebase.initializeApp({
  apiKey: "AIzaSyDtqMBea68TLGu66w-9anOuxbZVs0sHxfw",
  authDomain: "nexchat-d575d.firebaseapp.com",
  projectId: "nexchat-d575d",
  storageBucket: "nexchat-d575d.firebasestorage.app",
  messagingSenderId: "1074629915005",
  appId: "1:1074629915005:web:9618ddfcb8875c93921c14",
});

// The notifications service sends a webpush.notification payload, so the browser
// displays the notification itself — we only initialize messaging to receive it.
// Do NOT call showNotification here or every push would render twice.
firebase.messaging();
