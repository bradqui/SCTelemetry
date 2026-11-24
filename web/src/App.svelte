<script lang="ts">
  import { onMount, untrack } from "svelte";
  import type { PanelCtx } from "./lib/context";
  import { FleetConnection } from "./lib/fleet.svelte";
  import { fleetPick } from "./lib/fleetpick.svelte";
  import { LiveConnection } from "./lib/live.svelte";
  import { PrefsStore } from "./lib/prefs.svelte";
  import { applyTheme, DEFAULT_THEME, forcedTheme, THEME_BY_ID, themeForShip } from "./lib/themes";
  import { Trends } from "./lib/trends.svelte";
  import Customize from "./components/Customize.svelte";
  import Dashboard from "./components/Dashboard.svelte";
  import LocalFleet from "./components/LocalFleet.svelte";
  import ReplayBar from "./components/ReplayBar.svelte";
  import TopBar from "./components/TopBar.svelte";

  const live = new LiveConnection();
  const trends = new Trends();
  const store = new PrefsStore();
  const prefs = $derived(store.value);

  let now = $state(Date.now());
  onMount(() => {
    const stop = live.start();
    const timer = setInterval(() => (now = Date.now()), 1000);
    const onHash = () => (fleetOpen = location.hash === "#fleet");
    addEventListener("hashchange", onHash);
    return () => {
      stop();
      clearInterval(timer);
      removeEventListener("hashchange", onHash);
    };
  });

  // The fleet, in this page (#fleet): the agent relays the hub's fleet stream.
  let fleetOpen = $state(location.hash === "#fleet");
  let pushed = false; // we added the #fleet entry, so Back returns to the cockpit
  function showFleet(on: boolean) {
    if (on === fleetOpen) return;
    if (on) {
      pushed = true;
      location.hash = "#fleet";
    } else if (pushed) {
      pushed = false;
      history.back();
    } else {
      history.replaceState(null, "", location.pathname + location.search);
      fleetOpen = false;
    }
  }

  // -- view mode and customizing

  function initialCompact(): boolean {
    const q = new URLSearchParams(location.search);
    if (q.has("compact")) return q.get("compact") !== "0";
    try {
      return localStorage.getItem("ft.compact") === "1";
    } catch {
      return false;
    }
  }
  let compact = $state(initialCompact());
  let customizing = $state(new URLSearchParams(location.search).has("customize"));
  // Which settings tab opens: "Join a fleet" buttons (Wingmates, the fleet view) ask for
  // the Agent tab with a "ft:settings" event.
  let settingsTab = $state<"dashboard" | "agent">(
    new URLSearchParams(location.search).get("customize") === "agent" ? "agent" : "dashboard",
  );
  function openSettings(tab: "dashboard" | "agent") {
    if (fleetOpen) showFleet(false);
    settingsTab = tab;
    customizing = true;
  }
  onMount(() => {
    const onAsk = (e: Event) => openSettings((e as CustomEvent).detail === "agent" ? "agent" : "dashboard");
    addEventListener("ft:settings", onAsk);
    return () => removeEventListener("ft:settings", onAsk);
  });
  function toggleCompact() {
    compact = !compact;
    try {
      localStorage.setItem("ft.compact", compact ? "1" : "0");
    } catch {
      /* storage unavailable: fine */
    }
  }

  // -- effects

  // Trends read and write their own state: untrack so only the inputs re-run these.
  $effect(() => {
    const seed = live.trendSeed;
    untrack(() => trends.seed(seed));
  });
  $effect(() => {
    const snap = live.snapshot;
    untrack(() => trends.push(snap));
  });
  $effect(() => {
    if (live.resets) untrack(() => trends.clear());
  });
  $effect(() => {
    JSON.stringify(store.value); // track every preference
    store.save();
  });
  // The theme: the maker of the ship you're in (when matching is on), else your default.
  const forced = forcedTheme();
  const theme = $derived(
    forced.theme ??
      (prefs.matchShip ? themeForShip(live.snapshot?.ship?.class) : null) ??
      THEME_BY_ID[prefs.theme] ??
      THEME_BY_ID[DEFAULT_THEME],
  );
  $effect(() => {
    const root = document.documentElement;
    applyTheme(root, theme, forced.scheme ?? prefs.scheme);
    root.classList.toggle("fx", prefs.effects);
  });

  // Wingmates: the fleet, relayed by the agent, only while that panel is on screen.
  const wingShown = $derived(
    !fleetOpen &&
      Object.keys(live.uplinks).length > 0 &&
      (compact ? prefs.compact : prefs.full).some((s) => s.id === "wingmates" && !s.hidden),
  );
  let wing = $state<FleetConnection | null>(null);
  $effect(() => {
    fleetPick.setFrom(live.uplinks);
  });
  $effect(() => {
    if (!wingShown) return;
    const w = new FleetConnection({ local: true, hub: fleetPick.hub });
    const stop = w.start();
    wing = w;
    return () => {
      stop();
      wing = null;
    };
  });

  const snap = $derived(live.snapshot);
  const ship = $derived(snap?.ship ?? null);
  const waiting = $derived(live.socket !== "open" || !live.agent?.streaming || !snap);
  const ctx = $derived<PanelCtx | null>(
    snap ? { snap, ship, events: live.events, trends, prefs, compact, now, wing } : null,
  );
</script>

{#if fleetOpen}
  <LocalFleet {store} onBack={() => showFleet(false)} />
{:else}
<main class:compact class:replay={live.replay}>
  <TopBar
    socket={live.socket}
    agent={live.agent}
    snapshot={snap}
    {compact}
    replay={live.replay}
    caution={prefs.caution}
    uplinks={Object.values(live.uplinks)}
    onToggleCompact={toggleCompact}
    onCustomize={() => (customizing ? (customizing = false) : openSettings("dashboard"))}
    onFleet={() => showFleet(true)}
  />

  {#if waiting || !ctx}
    <section class="waiting">
      <div class="radar" aria-hidden="true"><span></span><i></i></div>
      {#if live.socket !== "open"}
        <h1>Can't reach the agent</h1>
        <p>Start it with <code>python -m starglance run</code>. This page reconnects by itself.</p>
      {:else if live.agent?.connected}
        <h1>Connected to Star Citizen</h1>
        <p>Load into the game and your telemetry will appear here.</p>
      {:else}
        <h1>Waiting for Star Citizen</h1>
        <p>{live.agent?.message ?? "Starting"}. Telemetry must be switched on and the game running.</p>
      {/if}
    </section>
  {:else}
    <Dashboard {ctx} layout={compact ? prefs.compact : prefs.full} editing={customizing} />
  {/if}

</main>

{/if}

{#if live.replay && !fleetOpen}
  <ReplayBar {live} />
{/if}

{#if customizing && !fleetOpen}
  <Customize {store} {compact} agent uplinks={live.uplinks} tab={settingsTab} onClose={() => (customizing = false)} />
{/if}

<style>
  main {
    max-width: 1920px;
    margin: 0 auto;
    padding: 8px clamp(8px, 1.2vw, 16px) 12px;
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    gap: var(--gap);
  }
  main.compact {
    max-width: 540px;
    padding: 6px 10px 12px;
    gap: 10px;
  }
  main.replay {
    padding-bottom: 96px;
  }
  .waiting {
    display: grid;
    justify-items: center;
    text-align: center;
    padding: 72px 24px;
    gap: 6px;
    border: 1px solid var(--line);
    border-radius: var(--radius);
    background: linear-gradient(180deg, var(--panel-2), var(--panel));
  }
  .waiting h1 {
    margin: 22px 0 0;
    font-size: 1.5rem;
  }
  .waiting p {
    margin: 0;
    color: var(--text-2);
    max-width: 46ch;
  }
  code {
    font-family: var(--mono);
    background: var(--bg-2);
    border: 1px solid var(--line);
    border-radius: 6px;
    padding: 1px 6px;
    font-size: 0.9em;
  }
  .radar {
    width: 110px;
    height: 110px;
    border-radius: 50%;
    border: 1px solid var(--line-2);
    background:
      radial-gradient(circle, transparent 54%, var(--line) 55%, transparent 56%),
      radial-gradient(circle, transparent 26%, var(--line) 27%, transparent 28%),
      linear-gradient(90deg, transparent 49.5%, var(--line) 50%, transparent 50.5%),
      linear-gradient(0deg, transparent 49.5%, var(--line) 50%, transparent 50.5%);
    position: relative;
    overflow: hidden;
  }
  .radar span {
    position: absolute;
    inset: 0;
    background: conic-gradient(from 0deg, var(--accent-dim), transparent 25%);
    animation: spin 2.4s linear infinite;
  }
  .radar i {
    position: absolute;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    left: 66%;
    top: 30%;
    background: var(--accent);
    box-shadow: 0 0 10px var(--accent);
    animation: pulse 2.4s ease-in-out infinite;
  }
  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
</style>
