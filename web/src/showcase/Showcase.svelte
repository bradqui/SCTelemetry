<script lang="ts">
  import { onMount } from "svelte";
  import Board from "../components/fleet/Board.svelte";
  import { DemoFleet, type DemoData } from "../lib/demo-fleet.svelte";
  import { usePageZoom } from "../lib/pagezoom.svelte";
  import { PrefsStore } from "../lib/prefs.svelte";
  import { applyTheme, palette, THEME_BY_ID, THEMES } from "../lib/themes";
  import type { Account, HubMode } from "../lib/types";
  // The write-up around a live demo: the real fleet page, on recorded telemetry
  // (demo-fleet.json beside the page: tools/demo_fleet.py).
  let data = $state.raw<DemoData | null>(null);
  let fleet = $state.raw<DemoFleet | null>(null);
  let loadError = $state("");
  const store = new PrefsStore();
  store.value.theme = "SG";
  store.value.scheme = "dark";
  store.value.matchShip = true;
  const prefs = $derived(store.value);
  usePageZoom(() => ({ scale: prefs.scale })); // big screens, like the real fleet page

  const me = $derived.by<Account | null>(() => {
    const row = data?.members.find((m) => m.id === data?.me);
    return row
      ? { id: row.id, name: row.name, avatar: null, role: "admin", active: true, discord: false, created_at: 0 }
      : null;
  });
  const mode = $derived<HubMode | null>(
    data && me
      ? { mode: "fleet", hub_version: "0.1.0", org: data.org, me, discord: false, dev_login: false, setup: false }
      : null,
  );

  onMount(async () => {
    try {
      const r = await fetch("./demo-fleet.json");
      data = (await r.json()) as DemoData;
      fleet = new DemoFleet(data);
    } catch {
      loadError = "The demo data didn't load. Reload the page to try again.";
    }
    // The page around the demo wears the RSI theme's tokens, without its details.
    const root = document.documentElement;
    applyTheme(root, THEME_BY_ID.RSI, "dark");
    delete root.dataset.deco;
    // #ace, #rook...: open that pilot (a link straight to someone)
    const named = pilots.find((p) => `#${p.who.toLowerCase()}` === location.hash.toLowerCase());
    if (named) setTimeout(() => openPilot(named.id), 50);
  });

  const pilots = [
    { id: "m_rook", who: "Rook", what: "Aegis Gladius, in a dogfight: three kills and a contract" },
    { id: "m_ace", who: "Ace", what: "Drake Cutlass Black, quantum jumping to Bounty Beacon" },
    { id: "m_kestrel", who: "Kestrel", what: "RSI Constellation, moving between seats, with Wren as co-pilot" },
    { id: "m_vale", who: "Vale", what: "Anvil Hornet, leaving an armistice zone" },
    { id: "m_mara", who: "Mara", what: "MISC Freelancer, landing and climbing out" },
    { id: "m_nova", who: "Nova", what: "on foot in a spaceport" },
  ];
  function openPilot(id: string) {
    fleet?.open(id);
    document.getElementById("demo")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }
</script>

<div class="page">
  <header class="hero">
    <p class="eyebrow">Star Citizen · ship and crew status</p>
    <h1 class="display">Starglance</h1>
    <p class="lede">
      Live ship and crew status for your org, read from Star Citizen's own telemetry. Your own cockpit screen on a second
      monitor or VR overlay, and the whole fleet at a glance on one page: who's flying what, where, in which mode, with
      which warnings.
    </p>
    <p class="links">
      <a href="./cockpit.html">Try the cockpit view</a><span aria-hidden="true">·</span><a href="../">Docs and guide</a
      ><span aria-hidden="true">·</span><a href="https://github.com/bradqui/starglance/releases/latest">Download</a>
    </p>
    <ul class="facts">
      <li><b>Reads only what the game offers</b> its local telemetry stream and log file; no memory reading, nothing near Easy Anti-Cheat</li>
      <li><b>You choose what's shared</b> eight categories, each one yours to switch off</li>
      <li><b>Your org runs its own hub</b> open source and self-hosted: no central service</li>
    </ul>
  </header>

  <section class="demo-section" id="demo">
    <div class="demo-head">
      <div>
        <h2 class="display">Try it</h2>
        <p>
          This is the real fleet page, running on telemetry recorded in game and played on a loop. The cards show
          everyone's numbers at a glance; click anyone to open their live dashboard. Pick a theme below: with <b>Match the ship</b> on, each pilot shows up in
          the theme of the ship they're flying.
        </p>
      </div>
      <div class="switcher" aria-label="Theme">
        <div class="row">
          <span class="lbl">Scheme</span>
          <div class="seg">
            <button class:on={prefs.scheme === "dark"} aria-pressed={prefs.scheme === "dark"} onclick={() => (prefs.scheme = "dark")}
              >Dark</button
            >
            <button class:on={prefs.scheme === "light"} aria-pressed={prefs.scheme === "light"} onclick={() => (prefs.scheme = "light")}
              >Light</button
            >
          </div>
          <label class="check"><input type="checkbox" bind:checked={prefs.matchShip} /> Match the ship each pilot is in</label>
        </div>
        <span class="lbl">Your theme</span>
        <div class="brands" role="radiogroup" aria-label="Your theme">
          {#each THEMES as t (t.id)}
            {@const p = palette(t, prefs.scheme)}
            <button
              class="brand"
              class:on={prefs.theme === t.id}
              role="radio"
              aria-checked={prefs.theme === t.id}
              onclick={() => (prefs.theme = t.id)}
              title="{t.name}: {t.tagline}"
            >
              <span class="sw" style:background="linear-gradient(135deg, {p.panel} 0 50%, {p.accent} 50%)"></span>{t.short}
            </button>
          {/each}
        </div>
      </div>
    </div>

    <div class="frame">
      {#if fleet && mode && me}
        <Board {mode} {me} source={fleet} {store} embedded defaultView="cards" />
      {:else}
        <p class="loading">{loadError || "Loading the fleet…"}</p>
      {/if}
    </div>

    <div class="pilots">
      <span class="lbl">Who's in the demo</span>
      {#each pilots as p (p.id)}
        <button onclick={() => openPilot(p.id)}><b>{p.who}</b> {p.what}</button>
      {/each}
      <span class="note">Plus Pike (agent running, not in game) and Juno (offline). Ship names are relabelled to show more makers; the telemetry is as recorded.</span>
    </div>
  </section>

  <section>
    <h2 class="display">How it fits together</h2>
    <div class="flow" aria-label="How the parts connect">
      <div class="node"><b>Star Citizen</b><span>Telemetry stream on your PC, plus its Game.log</span></div>
      <div class="arrow" aria-hidden="true">→</div>
      <div class="node accent"><b>Agent</b><span>On each player's PC: reads the game, shows your cockpit view, sends what you share</span></div>
      <div class="arrow" aria-hidden="true">→</div>
      <div class="node accent"><b>Hub</b><span>On your org's server: accounts and invites, the fleet page, an API for bots</span></div>
      <div class="arrow" aria-hidden="true">→</div>
      <div class="node"><b>Everyone</b><span>Fleet page in any browser or phone; Discord bots through the API</span></div>
    </div>
    <p class="small">
      The agent only ever connects out. Nobody opens ports, and nothing goes from the server back to anyone's game.
    </p>
  </section>

  <section class="cols">
    <div>
      <h2 class="display">On your PC</h2>
      <p>The agent reads two things the game already writes for this kind of use:</p>
      <ul>
        <li>
          <b>The telemetry stream</b> (switched on with one line in <code>user.cfg</code>; the agent does it and can undo it
          exactly): ship, flight, power, warning lights, weapons, fuel, vitals, seat and role, about 17 times a second.
        </li>
        <li>
          <b>Game.log</b>: where you are (armistice, jurisdiction, monitored space, server), quantum routes, contracts and
          objectives, rewards, ships destroyed by or near you, injuries.
        </li>
      </ul>
      <p>It works out what the game doesn't say outright: quantum travel, NAV or SCM, takeoff and landing, crews.</p>
    </div>
    <div>
      <h2 class="display">Your cockpit view</h2>
      <ul>
        <li>A live dashboard on <code>127.0.0.1</code>: heading, flight, ship, warnings, fuel, power, weapons, vitals, contract, activity, trends.</li>
        <li>Customize everything: Pilot, Combat, Explorer and Minimal layouts; show, hide, resize and drag panels.</li>
        <li>A compact layout sized for VR overlays (OVR Toolkit, XSOverlay).</li>
        <li>Replay recorded sessions with a timeline of every event, to try layouts without the game.</li>
        <li>The master warning lives in the header, so nothing on screen moves when it fires.</li>
      </ul>
    </div>
  </section>

  <section class="cols">
    <div>
      <h2 class="display">The fleet page</h2>
      <ul>
        <li><b>Roster</b> by ship (crews together under their pilot), by server (who you can actually meet in game), or by status.</li>
        <li><b>Member detail</b>: anyone's live dashboard, the same panels as your own.</li>
        <li><b>Fleet alarms</b> in the header: anyone's master warning or a bad injury, one click to their screen.</li>
        <li><b>Cards</b>: everyone's numbers side by side for flying together. Speed, altitude, climb rate, heading, G, fuel and quantum destination in a ship; health, oxygen, food, water and injuries on foot.</li>
        <li><b>Overview</b>: session totals, ships out with their crews, and everyone's activity as it happens.</li>
        <li>Works on phones: the roster is the page, a member opens full screen.</li>
      </ul>
    </div>
    <div>
      <h2 class="display">Themes</h2>
      <ul>
        <li>Seventeen themes, one per ship maker: colours, typefaces, corners and the details that make each brand recognisable, like Drake's hazard stripes or Argo's metal frame.</li>
        <li>Dark or light, your choice; everything else comes from the manufacturer.</li>
        <li>Optional: switch to the maker of whatever you board, and back to your default on foot.</li>
        <li>Kruger and Gatac follow their in-game screens and Argo its documented orange UI. The rest interpret the lore, to be tuned with screenshots from the game.</li>
      </ul>
    </div>
  </section>

  <section class="cols">
    <div>
      <h2 class="display">Joining</h2>
      <ul>
        <li>An admin sends an invite link. On your gaming PC: <code>starglance link &lt;invite&gt;</code> makes your account (named after your in-game handle unless you pick another) and links the PC in one step.</li>
        <li>Open the fleet page from the agent, already signed in. On a phone, type a short code from a signed-in device.</li>
        <li>No passwords anywhere, and no Discord needed. Discord sign-in can be switched on as an extra.</li>
        <li>Admins: invites with use limits and expiry, suspend or remove members (with their history), make other admins.</li>
      </ul>
    </div>
    <div>
      <h2 class="display">What gets shared</h2>
      <table>
        <tbody>
          <tr><th>status</th><td>in game, on foot or seated, your seat</td></tr>
          <tr><th>ship</th><td>ship, mode, warning lights, fuel, flight data</td></tr>
          <tr><th>weapons</th><td>guns ready, countermeasures</td></tr>
          <tr><th>vitals</th><td>health, oxygen, injuries</td></tr>
          <tr><th>uec</th><td>aUEC and contract rewards</td></tr>
          <tr><th>location</th><td>zone, jurisdiction, server, planet or moon, landing area, quantum destination</td></tr>
          <tr><th>mission</th><td>current contracts and objectives</td></tr>
          <tr><th>combat</th><td>kills, ships lost, session counts</td></tr>
        </tbody>
      </table>
      <p class="small">
        All on by default; anything you switch off never leaves your PC. Never collected: world coordinates, chat and party
        channels, anything outside the game's telemetry and log. Whoever runs the hub can see what you share.
      </p>
    </div>
  </section>

  <section class="cols">
    <div>
      <h2 class="display">For bots and tools</h2>
      <p>
        Admins make API keys on the page. With one, a Discord bot or script can read the roster and anyone's live state,
        follow every event as it happens (warnings, kills, contracts, quantum jumps), and hand out invites: enough to build a
        <code>!fleet</code> command, readiness checks and alerts.
      </p>
    </div>
    <div>
      <h2 class="display">Running a hub</h2>
      <p>
        One Docker container on one port behind an https proxy, about ten minutes to set up. The first start prints a link
        that makes you admin. Open source under the MIT license.
      </p>
    </div>
  </section>

  <section class="status">
    <h2 class="display">Where it's at</h2>
    <div class="cols">
      <div>
        <h3>Built and tested</h3>
        <ul>
          <li>The Windows app: its own window and tray icon, one-click updates</li>
          <li>The cockpit view, with the fleet and a Wingmates panel inside it, and on a tablet at home</li>
          <li>Hub with invites, admin tools, the fleet page and the bot API</li>
          <li>The seventeen themes</li>
          <li>About 250 automated tests on recorded sessions; the server image builds and starts in CI</li>
        </ul>
      </div>
      <div>
        <h3>Next</h3>
        <ul>
          <li>Ops with after-action summaries</li>
          <li>Tune the themes from in-game screenshots of each maker's screens</li>
          <li>More from the game as CIG adds it (hull and shield levels)</li>
        </ul>
      </div>
    </div>
  </section>

  <footer>
    <p>
      Not affiliated with Cloud Imperium Games. Star Citizen is a trademark of Cloud Imperium Rights LLC. Source:
      <a href="https://github.com/bradqui/starglance" target="_blank" rel="noopener">github.com/bradqui/starglance</a>
    </p>
  </footer>
</div>

<style>
  :global(html),
  :global(body) {
    background: var(--bg);
  }
  .page {
    max-width: 1440px;
    margin: 0 auto;
    padding: 28px max(16px, env(safe-area-inset-right, 0px)) 48px max(16px, env(safe-area-inset-left, 0px));
    display: grid;
    gap: 36px;
    color: var(--text);
    font-family: var(--font);
    line-height: 1.55;
  }
  .display {
    font-family: var(--font-display);
    font-weight: var(--display-weight);
    letter-spacing: var(--display-spacing);
  }
  h1 {
    font-size: clamp(2.2rem, calc(5vw / var(--z, 1)), 3.6rem);
    line-height: 1.05;
    margin: 4px 0 10px;
  }
  h2 {
    font-size: 1.45rem;
    margin: 0 0 10px;
    text-wrap: balance;
  }
  h3 {
    font-size: 0.72rem;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--text-3);
    margin: 0 0 6px;
  }
  p {
    margin: 0 0 10px;
    color: var(--text-2);
    max-width: 72ch;
  }
  p b,
  li b {
    color: var(--text);
  }
  ul {
    margin: 0;
    padding-left: 18px;
    display: grid;
    gap: 6px;
    color: var(--text-2);
  }
  code {
    font-family: var(--mono);
    font-size: 0.85em;
    background: var(--bg-2);
    border: 1px solid var(--line);
    border-radius: 3px;
    padding: 0 4px;
    color: var(--text);
    overflow-wrap: anywhere;
  }
  a {
    color: var(--accent);
  }
  .small {
    font-size: 0.88rem;
    color: var(--text-3);
  }
  .eyebrow {
    margin: 0;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--accent);
  }
  .lede {
    font-size: 1.12rem;
    color: var(--text-2);
    max-width: 68ch;
  }
  .links {
    display: flex;
    flex-wrap: wrap;
    gap: 6px 10px;
    margin: 4px 0 0;
    font-weight: 700;
  }
  .links span {
    color: var(--text-3);
  }
  .facts {
    list-style: none;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 8px;
    margin-top: 16px;
  }
  .facts li {
    border: 1px solid var(--line);
    border-top: 2px solid var(--accent);
    background: var(--panel);
    border-radius: 4px;
    padding: 10px 12px;
    font-size: 0.88rem;
  }
  .facts li b {
    display: block;
    margin-bottom: 2px;
  }

  /* demo */
  .demo-section {
    display: grid;
    gap: 12px;
  }
  .demo-head {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 560px);
    gap: 20px;
    align-items: end;
  }
  .switcher {
    display: grid;
    gap: 6px;
    padding: 10px 12px;
    border: 1px solid var(--line);
    border-radius: 6px;
    background: var(--panel);
  }
  .row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px 14px;
    align-items: center;
  }
  .lbl {
    font-size: 0.64rem;
    font-weight: 700;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--text-3);
  }
  .seg {
    display: inline-flex;
    border: 1px solid var(--line-2);
    border-radius: 3px;
    overflow: hidden;
  }
  .seg button {
    border: 0;
    background: var(--bg-2);
    padding: 3px 12px;
    font-size: 0.82rem;
    cursor: pointer;
  }
  .seg button + button {
    border-left: 1px solid var(--line-2);
  }
  .seg button.on {
    background: var(--accent);
    color: var(--bg);
    font-weight: 700;
  }
  .check {
    display: inline-flex;
    gap: 6px;
    align-items: center;
    font-size: 0.86rem;
    color: var(--text-2);
    cursor: pointer;
  }
  .check input {
    accent-color: var(--accent);
  }
  .brands {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(96px, 1fr));
    gap: 4px;
  }
  .brand {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 6px;
    border: 1px solid var(--line-2);
    border-radius: 3px;
    background: var(--bg-2);
    font-size: 0.76rem;
    cursor: pointer;
    white-space: nowrap;
    overflow: hidden;
  }
  .brand:hover {
    border-color: var(--text-3);
  }
  .brand.on {
    border-color: var(--accent);
    box-shadow: inset 0 0 0 1px var(--accent);
  }
  .brand .sw {
    width: 14px;
    height: 14px;
    flex: none;
    border-radius: 2px;
    border: 1px solid var(--line-2);
  }
  button:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }
  .frame {
    height: min(900px, calc(92vh / var(--z, 1)));
    min-height: 640px;
    border: 1px solid var(--line-2);
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 30px 80px -30px rgb(0 0 0 / 0.8);
  }
  .loading {
    margin: 0;
    padding: 40px;
    color: var(--text-3);
  }
  .pilots {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    align-items: center;
  }
  .pilots button {
    border: 1px solid var(--line);
    background: var(--panel);
    border-radius: 3px;
    padding: 4px 10px;
    font-size: 0.82rem;
    color: var(--text-2);
    cursor: pointer;
  }
  .pilots button:hover {
    border-color: var(--accent);
  }
  .note {
    font-size: 0.8rem;
    color: var(--text-3);
    flex-basis: 100%;
  }

  /* sections */
  .cols {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 28px 40px;
  }
  .flow {
    display: flex;
    align-items: stretch;
    gap: 8px;
  }
  .node {
    flex: 1;
    display: grid;
    gap: 4px;
    align-content: start;
    padding: 12px 14px;
    border: 1px solid var(--line);
    background: var(--panel);
    border-radius: 4px;
  }
  .node.accent {
    border-color: color-mix(in srgb, var(--accent) 55%, transparent);
    background: color-mix(in srgb, var(--accent) 7%, var(--panel));
  }
  .node b {
    font-family: var(--font-display);
    font-size: 1.05rem;
  }
  .node span {
    font-size: 0.85rem;
    color: var(--text-2);
  }
  .arrow {
    align-self: center;
    color: var(--accent);
    font-size: 1.4rem;
  }
  table {
    border-collapse: collapse;
    width: 100%;
    font-size: 0.86rem;
    margin-bottom: 10px;
  }
  th {
    text-align: left;
    font-family: var(--mono);
    font-weight: 500;
    color: var(--accent);
    padding: 4px 12px 4px 0;
    white-space: nowrap;
    vertical-align: top;
  }
  td {
    color: var(--text-2);
    padding: 4px 0;
    border-bottom: 1px solid var(--line);
  }
  .status {
    border: 1px solid var(--line);
    background: var(--panel);
    border-radius: 6px;
    padding: 18px 20px;
  }
  footer p {
    font-size: 0.82rem;
    color: var(--text-3);
    max-width: none;
  }

  @container page (max-width: 1100px) {
    .demo-head {
      grid-template-columns: minmax(0, 1fr);
    }
  }
  @container page (max-width: 860px) {
    .cols,
    .facts {
      grid-template-columns: minmax(0, 1fr);
    }
    .flow {
      flex-direction: column;
    }
    .arrow {
      transform: rotate(90deg);
    }
    .frame {
      height: auto;
      min-height: 0;
    }
  }
</style>
