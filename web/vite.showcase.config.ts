import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";

// The demo pages (npm run build:showcase), published on GitHub Pages under /demo/:
//   index.html    the real fleet page on recorded data, with a write-up around it
//   cockpit.html  the real cockpit view playing a recorded session, with the replay bar
// Relative paths, so they work from any folder or host. Needs the data first:
//   uv run python tools/demo_fleet.py && uv run python tools/demo_cockpit.py
const __dirname = dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [svelte()],
  root: resolve(__dirname, "demo"),
  base: "./",
  // web/showcase/ holds demo-fleet.json and demo-cockpit.json; they're copied next to the pages.
  publicDir: resolve(__dirname, "showcase"),
  build: {
    outDir: resolve(__dirname, "dist-showcase"),
    emptyOutDir: true,
    target: "es2022",
    rollupOptions: {
      input: { index: resolve(__dirname, "demo/index.html"), cockpit: resolve(__dirname, "demo/cockpit.html") },
    },
  },
});
