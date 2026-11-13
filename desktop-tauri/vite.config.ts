import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Porta fixa: a casca Tauri (src-tauri/tauri.conf.json > build.devUrl) e o servidor do nucleo
// (desktop/server.py > DEV_ORIGINS, com --dev) contam com ela.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  clearScreen: false,
  server: { port: 1420, strictPort: true, host: "127.0.0.1" },
  envPrefix: ["VITE_", "TAURI_ENV_"],
  build: {
    target: "es2022",
    sourcemap: false,
    rollupOptions: { input: { main: "index.html", mini: "mini.html" } },
  },
  test: { environment: "node" },
});
