// Starglance brand pack: the Wings emblem in Deep Space. SVG masters + every Discord PNG.
// Usage, from the repo root (needs site/ and web/ npm install): node brand/brand-export.cjs [out dir]
// The code is MIT; the artwork it draws is not (brand/LICENSE).
const fs = require("fs");
const path = require("path");
const ROOT = path.resolve(__dirname, "..");
const OUT = path.resolve(process.argv[2] || __dirname);
const { chromium } = require(path.join(ROOT, "site/node_modules/playwright-core"));

const C = { p: "#5fd4e8", s: "#f0b45c", g: "#0e131a", g2: "#1a2733", sky: "#0a1018", bad: "#ff4d5e", good: "#3ddc97" };
const LIGHT = { p: "#0b7f97", s: "#a8661a" }; // the house theme's light-mode pair, for white backgrounds

const f2 = (n) => +n.toFixed(2);
const pol = (r, deg, cx = 32, cy = 32) => { const a = (deg * Math.PI) / 180; return [f2(cx + r * Math.cos(a)), f2(cy + r * Math.sin(a))]; };
const star = (cx, cy, R, r, n = 5, rot = -90) => {
  let d = "";
  for (let i = 0; i < n * 2; i++) { const [x, y] = pol(i % 2 ? r : R, rot + (i * 180) / n, cx, cy); d += (i ? "L" : "M") + x + " " + y; }
  return d + "Z";
};

// ---------- the emblem ----------
const BARS = ["21,26.5 3,20.5 6.5,25.5 21,30.5", "21,33 7.5,28.5 10.5,33 21.5,37", "22.5,39.5 12.5,36.5 15.5,40.5 24,43"];
const mirror = (p) => p.split(" ").map((xy) => { const [x, y] = xy.split(","); return `${64 - +x},${y}`; }).join(" ");
const OPAC = [1, 0.72, 0.45];
function wings(p, s, { solidDiamond = null } = {}) {
  const bars = BARS.map((b, i) => `<g fill-opacity="${OPAC[i]}"><polygon points="${b}"/><polygon points="${mirror(b)}"/></g>`).join("");
  const diamondFill = solidDiamond ? `fill="${solidDiamond}"` : `fill="${p}" fill-opacity=".14"`;
  const inner = solidDiamond ? `<path d="M32 21 40 32 32 43 24 32Z" fill="${p}" fill-opacity=".14"/>` : "";
  return `<g fill="${p}">${bars}</g>` +
    `<path d="M32 15 44.5 32 32 49 19.5 32Z" ${diamondFill} stroke="${p}" stroke-width="3" stroke-linejoin="round"/>${inner}` +
    `<path d="${star(32, 32.5, 7.2, 2.9)}" fill="${s}"/>`;
}
const svgDoc = (inner, vb = "0 0 64 64") => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${vb}">${inner}</svg>\n`;
// On its ground: full-bleed square (Discord crops it to a circle; the wingtips stay inside).
function iconInner(scale = 0.86) {
  return `<defs><radialGradient id="bg" cx=".32" cy=".26" r=".95"><stop offset="0" stop-color="${C.g2}"/><stop offset="1" stop-color="${C.g}"/></radialGradient></defs>` +
    `<rect width="64" height="64" fill="url(#bg)"/>` +
    `<g transform="translate(32 32.6) scale(${scale}) translate(-32 -32)">${wings(C.p, C.s, { solidDiamond: C.g })}</g>`;
}

// ---------- emoji and role icons ----------
const EMOJI = {
  starglance: () => `<g transform="translate(32 32) scale(1.08) translate(-32 -32)">${wings(C.p, C.s, { solidDiamond: C.g })}</g>`,
  o7: () => `<rect x="4" y="12" width="56" height="40" rx="10" fill="${C.g}" stroke="${C.p}" stroke-width="3"/><text x="32" y="42" text-anchor="middle" font-family="Chakra Petch" font-weight="700" font-size="25" fill="${C.p}">o7</text>`,
  qt: () => `<g stroke="${C.p}" stroke-width="5" stroke-linecap="round"><path d="M10 21H33" stroke-opacity=".45"/><path d="M4 32H38"/><path d="M10 43H33" stroke-opacity=".45"/></g><circle cx="49" cy="32" r="9" fill="${C.s}"/>`,
  landed: () => `<g fill="none" stroke="${C.p}" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"><path d="M20 10 32 22 44 10" stroke-opacity=".45"/><path d="M20 24 32 36 44 24"/></g><path d="M10 50H54" stroke="${C.s}" stroke-width="6" stroke-linecap="round"/>`,
  gforce: () => `<g fill="none" stroke-width="7" stroke-linecap="round"><path d="M15.03 48.97A24 24 0 1 1 48.97 48.97" stroke="${C.bad}" stroke-opacity=".28"/><path d="M15.03 48.97A24 24 0 1 1 52.47 44.6" stroke="${C.bad}"/></g><text x="32" y="41" text-anchor="middle" font-family="Chakra Petch" font-weight="700" font-size="20" fill="${C.bad}">G</text>`,
  stale: () => `<g fill="none" stroke="${C.p}" stroke-width="5" stroke-linecap="round" stroke-opacity=".5"><path d="M10 28a31 31 0 0 1 44 0"/><path d="M19 37a18 18 0 0 1 26 0"/></g><circle cx="32" cy="46" r="4.5" fill="${C.p}" fill-opacity=".5"/><path d="M43 41 55 53M55 41 43 53" stroke="${C.bad}" stroke-width="5" stroke-linecap="round"/>`,
  fleet: () => `<path d="M32 7 43 26H21Z" fill="${C.s}" stroke="${C.s}" stroke-width="3" stroke-linejoin="round"/><path d="M16 33 27 52H5Z" fill="${C.p}" stroke="${C.p}" stroke-width="3" stroke-linejoin="round"/><path d="M48 33 59 52H37Z" fill="${C.p}" stroke="${C.p}" stroke-width="3" stroke-linejoin="round"/>`,
};
const ROLES = {
  developer: () => `<path d="M22 18 8 32l14 14M42 18l14 14-14 14" fill="none" stroke="${C.p}" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/><path d="M37 11 27 53" stroke="${C.s}" stroke-width="6" stroke-linecap="round"/>`,
  tester: () => `<path d="M17 45h30l4 7.5a2.5 2.5 0 0 1-2.2 3.5H15.2a2.5 2.5 0 0 1-2.2-3.5Z" fill="${C.s}"/><path d="M23 8h18M27 8v17L12.5 51a4 4 0 0 0 3.5 6h32a4 4 0 0 0 3.5-6L37 25V8" fill="none" stroke="${C.p}" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>`,
  "hub-host": () => `<g fill="none" stroke="${C.p}" stroke-width="4.5"><rect x="9" y="11" width="46" height="17" rx="4"/><rect x="9" y="36" width="46" height="17" rx="4"/></g><circle cx="19" cy="19.5" r="3.5" fill="${C.good}"/><circle cx="19" cy="44.5" r="3.5" fill="${C.good}"/><path d="M30 19.5h16M30 44.5h16" stroke="${C.p}" stroke-width="4" stroke-linecap="round" stroke-opacity=".5"/>`,
  member: () => `<g transform="translate(32 32) scale(1.08) translate(-32 -32)">${wings(C.p, C.s, { solidDiamond: C.g })}</g>`,
};

// ---------- artwork pages ----------
const fontUrl = (pkg, file) => "data:font/woff2;base64," + fs.readFileSync(path.join(ROOT, "web/node_modules/@fontsource", pkg, "files", file)).toString("base64");
const HEAD = `<style>
@font-face{font-family:"Chakra Petch";font-weight:600;src:url("${fontUrl("chakra-petch", "chakra-petch-latin-600-normal.woff2")}")}
@font-face{font-family:"Chakra Petch";font-weight:700;src:url("${fontUrl("chakra-petch", "chakra-petch-latin-700-normal.woff2")}")}
@font-face{font-family:"IBM Plex Sans";font-weight:400;src:url("${fontUrl("ibm-plex-sans", "ibm-plex-sans-latin-400-normal.woff2")}")}
@font-face{font-family:"IBM Plex Sans";font-weight:500;src:url("${fontUrl("ibm-plex-sans", "ibm-plex-sans-latin-500-normal.woff2")}")}
html,body{margin:0;background:transparent}
#a{position:relative;overflow:hidden}
#a canvas{position:absolute;inset:0}
.wm{font:700 1em/1 "Chakra Petch";letter-spacing:.08em;color:#f2f5f8}
.tg{font:500 1em/1.3 "IBM Plex Sans";color:#c9d4de;letter-spacing:.01em}
.ey{font:600 1em/1 "Chakra Petch";letter-spacing:.22em;color:${C.p}}
</style>`;
const SKY = `function rng(s){return()=>((s=(s*1664525+1013904223)>>>0)/4294967296)}
function sky(cv,seed,o){const w=cv.width,h=cv.height,x=cv.getContext("2d");const bg=x.createLinearGradient(0,0,0,h);bg.addColorStop(0,"${C.sky}");bg.addColorStop(1,"${C.g2}");x.fillStyle=bg;x.fillRect(0,0,w,h);
const r=rng(seed),n=Math.round(w*h/2600);for(let i=0;i<n;i++){const sx=r()*w,sy=r()*h,big=r()<.06;x.globalAlpha=.25+r()*.65;x.fillStyle=big&&r()<.5?"${C.p}":"#fff";x.beginPath();x.arc(sx,sy,(big?1.5:.55+r()*.5)*o.k,0,7);x.fill()}
x.globalAlpha=1;const cx=w*o.px,cy=h*o.py,rad=h*o.pr;x.save();x.shadowColor="${C.p}";x.shadowBlur=36*o.k;x.beginPath();x.arc(cx,cy,rad,0,7);x.fillStyle="${C.g}";x.fill();x.restore();
const rim=x.createLinearGradient(cx-rad,0,cx+rad*.4,0);rim.addColorStop(0,"rgba(0,0,0,0)");rim.addColorStop(.55,"${C.p}");rim.addColorStop(1,"rgba(0,0,0,0)");x.strokeStyle=rim;x.lineWidth=2.4*o.k;x.beginPath();x.arc(cx,cy,rad,Math.PI*1.02,Math.PI*1.98);x.stroke()}`;
const emblem = (size) => `<svg width="${size}" height="${size}" viewBox="0 0 64 64" style="flex:none">${wings(C.p, C.s, { solidDiamond: C.g })}</svg>`;

function art(w, h, seed, planet, body) {
  return `<!doctype html><html><head>${HEAD}</head><body><div id="a" style="width:${w}px;height:${h}px"><canvas width="${w}" height="${h}"></canvas>${body}</div>
<script>${SKY};sky(document.querySelector("canvas"),${seed},${JSON.stringify(planet)})</script></body></html>`;
}
const ART = {
  "discord/server-banner-960x540.png": () => art(960, 540, 7, { px: 0.95, py: 1.95, pr: 1.15, k: 1.4 },
    `<div style="position:absolute;left:84px;right:60px;top:150px;bottom:60px;display:flex;align-items:center;gap:30px">${emblem(190)}
     <div><div class="wm" style="font-size:66px">STARGLANCE</div><div class="tg" style="font-size:24px;margin-top:14px">Your ship and crew, at a glance</div></div></div>`),
  "discord/invite-background-1920x1080.png": () => art(1920, 1080, 21, { px: 0.78, py: 1.7, pr: 1.1, k: 2 },
    `<div style="position:absolute;left:96px;bottom:84px;display:flex;align-items:center;gap:26px;opacity:.9">${emblem(150)}
     <div><div class="wm" style="font-size:56px">STARGLANCE</div><div class="tg" style="font-size:22px;margin-top:10px">Your ship and crew, at a glance</div></div></div>`),
  "discord/welcome-header-1200x400.png": () => art(1200, 400, 33, { px: 0.98, py: 2.75, pr: 1.9, k: 1.4 },
    `<div style="position:absolute;inset:0 60px;display:flex;align-items:center;gap:40px">${emblem(210)}
     <div><div class="ey" style="font-size:22px">STARGLANCE</div><div class="wm" style="font-size:76px;margin-top:14px;white-space:nowrap">WELCOME ABOARD</div><div class="tg" style="font-size:22px;margin-top:16px">Your ship and crew, at a glance. Start in #help, show off in #show-your-dash.</div></div></div>`),
  "discord/rules-header-1200x400.png": () => art(1200, 400, 34, { px: 0.85, py: 2.3, pr: 1.7, k: 1.4 },
    `<div style="position:absolute;inset:0 60px;display:flex;align-items:center;gap:40px">${emblem(210)}
     <div><div class="ey" style="font-size:22px">STARGLANCE</div><div class="wm" style="font-size:96px;margin-top:14px">RULES</div><div class="tg" style="font-size:22px;margin-top:16px">Read these before you post.</div></div></div>`),
  "site/link-preview-1200x630.png": () => art(1200, 630, 12, { px: 0.9, py: 2.05, pr: 1.25, k: 1.6 },
    `<div style="position:absolute;left:90px;right:80px;top:0;bottom:40px;display:flex;align-items:center;gap:44px">${emblem(240)}
     <div><div class="wm" style="font-size:80px">STARGLANCE</div><div class="tg" style="font-size:30px;margin-top:18px">Your ship and crew, at a glance</div>
     <div class="tg" style="font-size:20px;margin-top:22px;color:#8fa0b2">Cockpit dashboard and live fleet page for Star Citizen. Free and open source.</div></div></div>`),
};

const page = (w, h, inner) => `<!doctype html><html><head>${HEAD}</head><body><div id="a" style="width:${w}px;height:${h}px"><svg width="${w}" height="${h}" viewBox="0 0 64 64">${inner}</svg></div></body></html>`;

(async () => {
  const w = (rel, text) => { const f = path.join(OUT, rel); fs.mkdirSync(path.dirname(f), { recursive: true }); fs.writeFileSync(f, text); };
  // SVG masters
  w("masters/starglance-wings.svg", svgDoc(wings(C.p, C.s)));
  w("masters/starglance-wings-on-light.svg", svgDoc(wings(LIGHT.p, LIGHT.s)));
  w("masters/starglance-wings-white.svg", svgDoc(wings("#ffffff", "#ffffff")));
  w("masters/starglance-icon.svg", svgDoc(iconInner()));

  const b = await chromium.launch();
  const shot = async (rel, html, wpx, hpx, transparent) => {
    const p = await b.newPage({ viewport: { width: wpx, height: hpx } });
    await p.setContent(html, { waitUntil: "load" });
    await p.evaluate(() => document.fonts.ready);
    await p.waitForTimeout(150);
    const f = path.join(OUT, rel);
    fs.mkdirSync(path.dirname(f), { recursive: true });
    await (await p.$("#a")).screenshot({ path: f, omitBackground: transparent });
    await p.close();
  };
  await shot("discord/server-icon-512.png", page(512, 512, iconInner()), 512, 512, false);
  await shot("discord/release-bot-avatar-512.png", page(512, 512, iconInner()), 512, 512, false);
  for (const [id, draw] of Object.entries(EMOJI)) await shot(`discord/emoji/${id}.png`, page(128, 128, draw()), 128, 128, true);
  for (const [id, draw] of Object.entries(ROLES)) await shot(`discord/role-icons/${id}.png`, page(64, 64, draw()), 64, 64, true);
  for (const [rel, make] of Object.entries(ART)) {
    const m = rel.match(/(\d+)x(\d+)/);
    await shot(rel, make(), +m[1], +m[2], false);
  }
  await b.close();
  console.log("done");
})();
