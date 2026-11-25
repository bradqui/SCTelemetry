// Build the live demos into public/demo/ (gitignored): the fleet page and the cockpit view
// on the bundled recordings. Needs uv and web/node_modules (npm install in web/).
//   npm run demo
import { execSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SITE = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const ROOT = path.resolve(SITE, "..");
const sh = (cmd, cwd = ROOT) => execSync(cmd, { cwd, stdio: "inherit" });

sh("uv run python tools/demo_fleet.py");
sh("uv run python tools/demo_cockpit.py");
sh("npm run build:showcase", path.join(ROOT, "web"));
const out = path.join(SITE, "public", "demo");
fs.rmSync(out, { recursive: true, force: true });
fs.cpSync(path.join(ROOT, "web", "dist-showcase"), out, { recursive: true });
console.log(`demo: ${path.relative(ROOT, out)}`);
