import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";

// The showcase page (npm run build:showcase): the real fleet page on recorded data, with a
// write-up around it. Relative paths, so it works from any folder or host.
// Needs web/showcase/demo-fleet.json: uv run python tools/demo_fleet.py
export default defineConfig({
  plugins: [svelte()],
  base: "./",
  build: {
    outDir: "dist-showcase",
    emptyOutDir: true,
    target: "es2022",
    rollupOptions: { input: "showcase.html" },
  },
});
