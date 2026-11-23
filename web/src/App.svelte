<script lang="ts">
  import { onMount } from "svelte";
  import { LiveConnection } from "./lib/live.svelte";
  import Cockpit from "./components/Cockpit.svelte";
  import EventFeed from "./components/EventFeed.svelte";
  import Personal from "./components/Personal.svelte";
  import TopBar from "./components/TopBar.svelte";

  const live = new LiveConnection();
  onMount(() => live.start());

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
  function toggleCompact() {
    compact = !compact;
    try {
      localStorage.setItem("ft.compact", compact ? "1" : "0");
    } catch {
      /* storage unavailable: fine */
    }
  }

  const snap = $derived(live.snapshot);
  const ship = $derived(snap?.ship ?? null);
  const waiting = $derived(live.socket !== "open" || !live.agent?.streaming || !snap);
</script>

<main class:compact>
  <TopBar
    socket={live.socket}
    agent={live.agent}
    snapshot={snap}
    {compact}
    onToggleCompact={toggleCompact}
  />

  {#if waiting}
    <section class="waiting panel">
      <div class="radar" aria-hidden="true"><span></span></div>
      {#if live.socket !== "open"}
        <h1>Can't reach the agent</h1>
        <p>Start it with <code>python -m fleet_agent run</code>. This page reconnects by itself.</p>
      {:else if live.agent?.connected}
        <h1>Connected to Star Citizen</h1>
        <p>Load into the game and your telemetry will appear here.</p>
      {:else}
        <h1>Waiting for Star Citizen</h1>
        <p>{live.agent?.message ?? "Starting"}. Telemetry must be switched on and the game running.</p>
      {/if}
    </section>
  {:else if snap}
    {#if ship}
      <Cockpit {ship} weapons={snap.weapons} {compact} />
    {:else if snap.status?.locomotion === "seated"}
      <section class="boarding panel">
        <span class="label">Boarding</span>
        <p>Seated. Ship systems appear in a moment.</p>
      </section>
    {/if}
    {#if snap.vitals && (!ship || !compact)}
      <Personal vitals={snap.vitals} status={snap.status} {compact} />
    {/if}
    {#if !compact}
      <EventFeed events={live.events} />
    {/if}
  {/if}

  {#if !compact}
    <footer>
      Local view · only this PC can open it{live.agentVersion ? ` · agent ${live.agentVersion}` : ""}
    </footer>
  {/if}
</main>

<style>
  main {
    max-width: 1440px;
    margin: 0 auto;
    padding: 10px clamp(12px, 2vw, 24px) 24px;
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    gap: var(--gap);
  }
  main.compact {
    max-width: 520px;
    padding: 6px 10px 12px;
    gap: 10px;
  }
  .waiting {
    display: grid;
    justify-items: center;
    text-align: center;
    padding: 64px 24px;
    gap: 6px;
  }
  .waiting h1 {
    margin: 18px 0 0;
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
    width: 84px;
    height: 84px;
    border-radius: 50%;
    border: 1px solid var(--line-2);
    background:
      radial-gradient(circle, transparent 54%, var(--line) 55%, transparent 56%),
      radial-gradient(circle, transparent 26%, var(--line) 27%, transparent 28%);
    position: relative;
    overflow: hidden;
  }
  .radar span {
    position: absolute;
    inset: 0;
    background: conic-gradient(from 0deg, var(--accent-dim), transparent 25%);
    animation: spin 2.4s linear infinite;
  }
  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
  .boarding p {
    margin: 0;
    color: var(--text-2);
  }
  footer {
    text-align: center;
    color: var(--text-3);
    font-size: 0.78rem;
    padding-top: 6px;
  }
</style>
