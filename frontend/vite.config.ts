import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The dev-server proxy target is resolved by the Node process running Vite,
// not by the browser. That process only runs where `npm run dev` runs:
//   - locally (`npm run dev` on your machine)  -> backend is on localhost:8000
//   - in Docker (frontend container)           -> backend is a SEPARATE
//     container, reachable at http://backend:8000 (its docker-compose
//     service name), NOT localhost. `localhost` inside the frontend
//     container refers to the frontend container itself, where nothing is
//     listening on :8000 - every /api and /ws call was silently failing
//     with a proxy error whenever the app was run via `docker compose up`,
//     which looked like "nothing loads / uploads do nothing" in the browser.
// docker-compose.yml sets these env vars for the frontend service so the
// same config file works in both environments; local dev falls back to
// localhost when the vars aren't set.
const apiTarget = process.env.VITE_API_PROXY_TARGET || "http://localhost:8000";
const wsTarget = process.env.VITE_WS_PROXY_TARGET || "ws://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: apiTarget,
        changeOrigin: true,
      },
      // Real-time detection feed (app/api/routes/ws.py) -- needs `ws: true` so Vite
      // upgrades the proxied connection instead of treating it as plain HTTP.
      "/ws": {
        target: wsTarget,
        ws: true,
        changeOrigin: true,
      },
    },
  },
});
