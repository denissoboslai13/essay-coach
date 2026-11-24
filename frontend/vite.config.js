import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Shown in the header, so you can tell which build is running (e.g. an old Docker image).
// In Docker the frontend and backend are built together, so this is also the backend's build time.
const buildTime = new Date().toISOString().slice(0, 16).replace("T", " ") + " UTC";

export default defineConfig(({ command }) => ({
  plugins: [react()],
  define: {
    __BUILD_LABEL__: JSON.stringify(command === "build" ? `build ${buildTime}` : "dev server"),
  },
  server: {
    port: 5173,
    // Requests to /api/* go to the FastAPI backend, so the browser never needs the API key
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
}));
