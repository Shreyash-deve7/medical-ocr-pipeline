import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const backendOrigin =
  (import.meta.env?.VITE_BACKEND_URL as string | undefined) ||
  "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: backendOrigin,
        // OCR / pipeline requests can take several minutes on a cold GPU;
        // give them a generous timeout so the proxy doesn't drop the
        // connection and surface a "Failed to fetch" in the frontend.
        timeout: 300000,
      },
    },
  },
});
