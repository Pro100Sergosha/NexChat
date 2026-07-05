import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

// Dev server proxy mirrors the production nginx routing so the app talks to
// same-origin paths (/api/auth, /api/chat, /ws) in both dev and prod. The
// backend routes live at root, so the /api/<svc> prefix is stripped.
//
// Targets are env-driven: default to localhost for a host-run `npm run dev`,
// and are overridden to the compose service names (auth:8000 / chat:8001)
// when the dev server runs inside docker.
const authTarget = process.env.AUTH_PROXY_TARGET ?? "http://localhost:8000";
const chatTarget = process.env.CHAT_PROXY_TARGET ?? "http://localhost:8001";
const wsTarget = process.env.CHAT_WS_TARGET ?? "ws://localhost:8001";
const notificationsTarget =
  process.env.NOTIFICATIONS_PROXY_TARGET ?? "http://localhost:8002";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    host: true,
    port: 5173,
    // Bind-mounted source from a Windows/WSL host doesn't emit inotify events;
    // poll instead when running in docker (VITE_USE_POLLING=1).
    watch: process.env.VITE_USE_POLLING
      ? { usePolling: true, interval: 100 }
      : undefined,
    proxy: {
      "/api/auth": {
        target: authTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/auth/, ""),
      },
      "/api/chat": {
        target: chatTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/chat/, ""),
      },
      "/ws": {
        target: wsTarget,
        ws: true,
      },
      // /api/notifications/events is SSE; http-proxy streams it fine.
      "/api/notifications": {
        target: notificationsTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/notifications/, ""),
      },
    },
  },
});
