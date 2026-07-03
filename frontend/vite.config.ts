import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

// Dev server proxy mirrors the production nginx routing so the app talks to
// same-origin paths (/api/auth, /api/chat, /ws) in both dev and prod.
// Backends run directly on 8000 (auth) and 8001 (chat) with routes at root,
// so the /api/<svc> prefix is stripped before proxying.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api/auth": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/auth/, ""),
      },
      "/api/chat": {
        target: "http://localhost:8001",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/chat/, ""),
      },
      "/ws": {
        target: "ws://localhost:8001",
        ws: true,
      },
    },
  },
});
