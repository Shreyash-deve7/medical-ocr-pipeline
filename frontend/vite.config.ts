import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const backendOrigin =
  (import.meta.env?.VITE_BACKEND_URL as string | undefined) ||
  "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": backendOrigin,
    },
  },
});
