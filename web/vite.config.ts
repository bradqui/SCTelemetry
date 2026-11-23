import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";

// `npm run dev` proxies the live data to a running agent (python -m fleet_agent run).
const agent = "http://127.0.0.1:8740";

export default defineConfig({
  plugins: [svelte()],
  base: "./",
  server: {
    port: 5173,
    proxy: {
      "/ws": { target: agent, ws: true, changeOrigin: true },
      "/api": { target: agent, changeOrigin: true },
    },
  },
  build: { outDir: "dist", emptyOutDir: true, target: "es2022" },
});
