// Screenshots and short clips for the docs, into site/public/shots/. The demo and clips
// groups are made fresh by the Pages workflow on every deploy (gitignored); the app group
// needs a running agent and hub, so it's made here when those screens change and its
// pictures (shots/app/) are committed.
//
//   npm run demo                 build the demo pages first (public/demo/)
//   npm run shots                demo + clips + app (everything)
//   npm run shots -- demo clips  just those groups
//
// Groups:
//   demo   the cockpit and fleet demos (recorded data, no servers)
//   clips  short looping videos (.webm) from the demos, with a poster (.jpg)
//   app    the real agent and hub on this PC, for what the demos can't show (Agent
//          settings, problem reports, the hub's admin): a test hub with test sign-in, a
//          fake game playing the bundled recordings, and an agent linked to it, all in a
//          temporary folder. The agent gets a fake StarCitizen folder and a made-up handle,
//          and its settings are shown with a generic install path, so nothing from this
//          PC's own game or name ends up in a picture. Takes about two minutes.
//
// Needs Playwright's Chromium once: npx playwright install chromium
// Look at every picture before committing it.

import { spawn } from "node:child_process";
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const SITE = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const ROOT = path.resolve(SITE, "..");
const PUBLIC = path.join(SITE, "public");
const OUT = path.join(PUBLIC, "shots");
const PORT = 4190;
const BASE = `http://127.0.0.1:${PORT}/starglance`;
const groups = process.argv.slice(2).length ? process.argv.slice(2) : ["demo", "clips", "app"];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

fs.mkdirSync(OUT, { recursive: true });

// -- a static server for public/ at /starglance/, as on GitHub Pages

const TYPES = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json",
  ".svg": "image/svg+xml", ".woff2": "font/woff2", ".woff": "font/woff", ".jpg": "image/jpeg", ".png": "image/png" };
function serve() {
  const server = http.createServer((req, res) => {
    const url = new URL(req.url, "http://x");
    let p = decodeURIComponent(url.pathname).replace(/^\/starglance/, "");
    if (p.endsWith("/")) p += "index.html";
    const file = path.join(PUBLIC, path.normalize(p));
    if (!file.startsWith(PUBLIC) || !fs.existsSync(file)) {
      res.writeHead(404).end();
      return;
    }
    res.writeHead(200, { "Content-Type": TYPES[path.extname(file)] ?? "application/octet-stream" });
    fs.createReadStream(file).pipe(res);
  });
  return new Promise((resolve) => server.listen(PORT, "127.0.0.1", () => resolve(server)));
}

// In the app pictures: the test hub's address reads as an example one, and the report
// shows a generic Windows version rather than this PC's.
async function tidy(page) {
  await page.evaluate(() => {
    const swap = (s) =>
      s
        .replaceAll("http://127.0.0.1:8190", "https://fleet.example.org")
        .replace(/Windows-\d+-[\d.]+-SP\d/g, "Windows-11-10.0.26100-SP0");
    const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let n = walk.nextNode(); n; n = walk.nextNode()) {
      const v = swap(n.nodeValue ?? "");
      if (v !== n.nodeValue) n.nodeValue = v;
    }
  });
}

async function shot(page, name, opts = {}) {
  if (name.startsWith("app/")) await tidy(page);
  const file = path.join(OUT, `${name}.jpg`);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const target = opts.el ? page.locator(opts.el).first() : page;
  await target.screenshot({ path: file, type: "jpeg", quality: 88, ...(opts.el ? {} : { fullPage: false }) });
  console.log(`  ${name}.jpg  ${Math.round(fs.statSync(file).size / 1024)} KB`);
}

async function ready(page) {
  await page.waitForSelector(".dash", { timeout: 20_000 });
  await sleep(1500); // fonts, gauges settling
}

// As in a live session (no replay bar), except where the replay bar is the subject.
const cockpit = (q) => `${BASE}/demo/cockpit.html?badge=0&live&${q}`;
const replay = (q) => `${BASE}/demo/cockpit.html?badge=0&${q}`;

// -- the demos

async function demoShots(browser) {
  console.log("demo");
  const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
  const page = await ctx.newPage();

  // Play a little first, so Trends and Activity have something in them.
  await page.goto(cockpit("at=192"));
  await ready(page);
  await sleep(12_000);
  await shot(page, "cockpit-pilot"); // still playing: a still is a still
  await shot(page, "cockpit-topbar", { el: "header.top" });

  await page.goto(cockpit("at=15&pause"));
  await ready(page);
  await shot(page, "cockpit-on-foot");

  await page.goto(cockpit("at=436&pause"));
  await ready(page);
  await shot(page, "header-warning", { el: "header.top" });

  await page.goto(cockpit("at=600&pause&customize"));
  await ready(page);
  await shot(page, "cockpit-customize");
  await page.locator("aside.drawer").getByRole("button", { name: /^Combat/ }).first().click();
  await page.locator("aside.drawer button.done").click();
  await sleep(800);
  await shot(page, "cockpit-combat");
  await page.goto(replay("at=600&pause"));
  await ready(page);
  await page.getByRole("button", { name: /Events/ }).first().click();
  await sleep(500);
  await shot(page, "replay-events");
  await ctx.close();

  // Themes, light, compact: a fresh context each (preferences live in localStorage).
  for (const [name, q] of [
    ["theme-drake", "theme=DRAK"],
    ["theme-anvil", "theme=ANVL"],
    ["theme-aegis", "theme=AEGS"],
    ["theme-misc", "theme=MISC"],
    ["theme-light", "theme=ORIG&scheme=light"],
  ]) {
    const c = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const p = await c.newPage();
    await p.goto(cockpit(`at=200&pause&${q}`));
    await ready(p);
    await shot(p, name);
    await c.close();
  }
  {
    const c = await browser.newContext({ viewport: { width: 520, height: 1000 } });
    const p = await c.newPage();
    await p.goto(cockpit("at=300&pause&compact=1"));
    await ready(p);
    await shot(p, "cockpit-compact");
    await c.close();
  }

  // The fleet demo: the board inside the showcase page.
  const f = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
  const fp = await f.newPage();
  await fp.goto(`${BASE}/demo/`);
  await fp.waitForSelector("#demo > .frame .board, #demo > .frame main, #demo > .frame section", { timeout: 20_000 });
  await sleep(4000);
  await shot(fp, "fleet-cards", { el: "#demo > .frame" });
  await fp.locator("#demo > .frame").getByRole("tab", { name: /Overview/ }).click();
  await sleep(1500);
  await shot(fp, "fleet-overview", { el: "#demo > .frame" });
  const fp2 = await f.newPage(); // a fresh load: the hash picks the pilot on start
  await fp2.goto(`${BASE}/demo/#ace`);
  await sleep(4000);
  await shot(fp2, "fleet-member", { el: "#demo > .frame" });
  await f.close();

  const ph = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true });
  const pp = await ph.newPage();
  await pp.goto(`${BASE}/demo/`);
  await sleep(4000);
  await shot(pp, "fleet-phone", { el: "#demo > .frame" });
  await ph.close();
}

// -- clips

async function clip(browser, name, size, run) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "sg-clip-"));
  const ctx = await browser.newContext({ viewport: size, recordVideo: { dir, size } });
  const page = await ctx.newPage();
  await run(page);
  const video = page.video();
  await ctx.close();
  const src = await video.path();
  fs.copyFileSync(src, path.join(OUT, `${name}.webm`));
  fs.rmSync(dir, { recursive: true, force: true });
  console.log(`  ${name}.webm  ${Math.round(fs.statSync(path.join(OUT, `${name}.webm`)).size / 1024)} KB`);
}

async function clips(browser) {
  console.log("clips");
  const size = { width: 1280, height: 720 };
  await clip(browser, "clip-replay", size, async (page) => {
    await page.goto(cockpit("at=275"));
    await ready(page);
    await shot(page, "clip-replay");
    await sleep(9000);
  });
  await clip(browser, "clip-themes", size, async (page) => {
    await page.goto(cockpit("at=300&pause&customize"));
    await ready(page);
    await shot(page, "clip-themes");
    const drawer = page.locator("aside.drawer");
    await drawer.getByText("Match the ship I'm in").click(); // or the ship's maker wins
    for (const t of ["Drake", "Anvil", "Aegis", "MISC", "Origin"]) {
      await drawer.getByRole("radio", { name: new RegExp(t, "i") }).first().click();
      await sleep(1600);
    }
  });
  await clip(browser, "clip-fleet", size, async (page) => {
    await page.goto(`${BASE}/demo/`);
    await page.locator("#demo > .frame").scrollIntoViewIfNeeded();
    await sleep(2500);
    await page.evaluate(() => document.querySelector("#demo > .frame")?.scrollIntoView({ block: "start" }));
    await sleep(500);
    await shot(page, "clip-fleet");
    await sleep(8000);
  });
}

// -- the real agent and hub

function start(name, cmd, args, env = {}) {
  const proc = spawn(cmd, args, { cwd: ROOT, env: { ...process.env, ...env }, shell: process.platform === "win32" });
  const log = fs.createWriteStream(path.join(os.tmpdir(), `sg-shots-${name}.log`));
  proc.stdout.pipe(log);
  proc.stderr.pipe(log);
  return proc;
}
function run(cmd, args, env = {}) {
  return new Promise((resolve, reject) => {
    const p = spawn(cmd, args, { cwd: ROOT, env: { ...process.env, ...env }, shell: process.platform === "win32", stdio: "inherit" });
    p.on("exit", (code) => (code === 0 ? resolve() : reject(new Error(`${cmd} ${args.join(" ")}: exit ${code}`))));
  });
}
async function until(url, ms = 60_000) {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    try {
      if ((await fetch(url)).ok) return;
    } catch {
      /* not up yet */
    }
    await sleep(500);
  }
  throw new Error(`${url} didn't come up`);
}
function kill(proc) {
  if (!proc || proc.exitCode !== null) return;
  if (process.platform === "win32") spawn("taskkill", ["/pid", String(proc.pid), "/T", "/F"]);
  else proc.kill("SIGTERM");
}

async function appShots(browser) {
  console.log("app (about two minutes)");
  if (!fs.existsSync(path.join(ROOT, "web", "dist", "index.html"))) await run("npm", ["run", "build", "--prefix", "web"]);
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "sg-shots-"));
  const hubUrl = "http://127.0.0.1:8190";
  const agentUrl = "http://127.0.0.1:8760";
  // A made-up game folder: the agent finds it first, so it never reads this PC's own Game.log.
  const live = path.join(tmp, "sc", "StarCitizen", "LIVE");
  fs.mkdirSync(live, { recursive: true });
  fs.writeFileSync(path.join(live, "Data.p4k"), "");
  fs.writeFileSync(
    path.join(live, "Game.log"),
    "<2026-11-25T18:00:00.000Z> [Notice] <Legacy login response> [CIG-net] User Login Success - Handle[Ace] - Time[1]\n",
  );
  const agentEnv = { STARGLANCE_HOME: path.join(tmp, "agent") };
  const procs = [];
  try {
    procs.push(
      start("hub", "uv", ["run", "python", "-m", "starglance_hub"], {
        HUB_DEV_LOGIN: "1",
        HUB_DATA_DIR: path.join(tmp, "hub"),
        HUB_PORT: "8190",
        HUB_URL: hubUrl,
        HUB_ORG_NAME: "Demo Fleet",
        HUB_WEB_DIR: path.join(ROOT, "web", "dist"),
      }),
    );
    procs.push(start("game", "uv", ["run", "python", "tools/replay.py", "--port", "2953"]));
    await until(`${hubUrl}/api/health`);

    // The admin, and a few members (test sign-in by name).
    const admin = await browser.newContext({ viewport: { width: 1400, height: 900 } });
    const ap = await admin.newPage();
    await ap.goto(`${hubUrl}/auth/dev?name=Rook`);
    for (const name of ["Kestrel", "Wren", "Vale"]) {
      const c = await browser.newContext();
      await (await c.newPage()).goto(`${hubUrl}/auth/dev?name=${name}`);
      await c.close();
    }
    const inv = await (await ap.request.post(`${hubUrl}/api/admin/invites`, { data: { uses: 5, days: 7 }, headers: { Origin: hubUrl } })).json();
    const invite = inv.url ?? inv.link ?? inv.invite;
    if (!invite) throw new Error(`No invite link in ${JSON.stringify(inv)}`);

    // Ace links a PC called "Gaming PC" (not this PC's name) and starts the agent.
    const link =
      "import sys, starglance.fleetlink as f; f.machine_name = lambda: 'Gaming PC'; " +
      "from starglance.__main__ import main; main(sys.argv[1:])";
    await run("uv", ["run", "python", "-c", `"${link}"`, "link", invite, "--name", "Ace", "--path", path.join(tmp, "sc", "StarCitizen")], agentEnv);
    procs.push(
      start("agent", "uv", ["run", "python", "-m", "starglance", "run", "--path", path.join(tmp, "sc", "StarCitizen"),
        "--channel", "LIVE", "--game-port", "2953", "--ui-port", "8760"], agentEnv),
    );
    await until(`${agentUrl}/api/agent/settings`);

    const agent = await browser.newContext({ viewport: { width: 1400, height: 900 } });
    // Show a generic install, whatever the agent found.
    await agent.route("**/api/agent/settings", async (route) => {
      const res = await route.fetch();
      const body = await res.json();
      body.installs = [{ channel: "LIVE", path: "C:\\Program Files\\Roberts Space Industries\\StarCitizen\\LIVE", telemetry: true, current: true }];
      body.suggested_name = "Ace";
      await route.fulfill({ response: res, json: body });
    });
    const page = await agent.newPage();
    await page.goto(agentUrl);
    await ready(page);
    console.log("  waiting 70 s for a minute of play in the recent buffer");
    await sleep(70_000);

    await page.goto(`${agentUrl}/?customize=agent`);
    await ready(page);
    await shot(page, "app/agent-settings", { el: "aside.drawer" });
    await page.locator("aside.drawer button.done").click();

    await page.request.post(`${agentUrl}/api/agent/report/mark`, { data: {}, headers: { Origin: agentUrl } });
    await sleep(1200);
    await shot(page, "app/topbar-marked", { el: "header.top" });
    await page.getByRole("button", { name: /marked/ }).first().click();
    await sleep(1500);
    await shot(page, "app/report-pick");
    await page.locator("textarea").first().fill("It showed two quantum jumps for one jump.");
    await page.getByRole("button", { name: /Preview|Next|Check/ }).last().click();
    await sleep(4000);
    await shot(page, "app/report-preview");
    await page.getByRole("button", { name: /^Send/ }).first().click();
    await sleep(2500);

    await page.goto(`${agentUrl}/#fleet`);
    await sleep(3500);
    await shot(page, "app/cockpit-fleet-view");

    // The hub, as the admin.
    await ap.goto(`${hubUrl}/?admin`);
    await sleep(2000);
    await shot(ap, "app/hub-admin-members");
    for (const [tab, name] of [["Invites", "app/hub-admin-invites"], ["Reports", "app/hub-admin-reports"]]) {
      await ap.getByRole("button", { name: new RegExp(`^${tab}`) }).first().click();
      await sleep(1200);
      if (tab === "Reports") {
        await ap.getByRole("button", { name: /^View/ }).first().click();
        await sleep(1200);
      }
      await shot(ap, name);
    }
    await ap.goto(`${hubUrl}/?account`);
    await sleep(2000);
    await shot(ap, "app/hub-account");

    // The invite page, as a new member sees it.
    const guest = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const gp = await guest.newPage();
    await gp.goto(invite);
    await sleep(2000);
    await shot(gp, "app/hub-join");
  } finally {
    procs.forEach(kill);
    await sleep(1500);
    fs.rmSync(tmp, { recursive: true, force: true, maxRetries: 5, retryDelay: 500 });
  }
}

// --

const server = await serve();
const browser = await chromium.launch();
try {
  if (groups.includes("demo") || groups.includes("clips")) {
    if (!fs.existsSync(path.join(PUBLIC, "demo", "cockpit.html"))) throw new Error("Build the demo first: npm run demo");
  }
  if (groups.includes("demo")) await demoShots(browser);
  if (groups.includes("clips")) await clips(browser);
  if (groups.includes("app")) await appShots(browser);
} finally {
  await browser.close();
  server.close();
}
