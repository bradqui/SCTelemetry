<script lang="ts">
  import type { AgentState, Snapshot } from "../lib/types";
  const ROLE: Record<string, string> = {
    pilot: "Pilot",
    copilot: "Co-pilot",
    gunner: "Gunner",
    crew: "Crew",
  };

  let {
    socket,
    agent,
    snapshot,
    compact,
    onToggleCompact,
  }: {
    socket: "connecting" | "open" | "closed";
    agent: AgentState | null;
    snapshot: Snapshot | null;
    compact: boolean;
    onToggleCompact: () => void;
  } = $props();

  const live = $derived(socket === "open" && agent?.streaming);
  const statusText = $derived(
    socket !== "open" ? "Agent offline" : agent?.streaming ? "Live" : (agent?.message ?? "Connecting"),
  );
  const ship = $derived(snapshot?.ship ?? null);
  const status = $derived(snapshot?.status ?? null);
</script>

<header class="top" class:compact>
  <div class="brand">
    <svg viewBox="0 0 32 32" aria-hidden="true"><path d="M16 3 29 27H3z" /><circle cx="16" cy="20" r="3" /></svg>
    {#if !compact}<span>Fleet Telemetry</span>{/if}
  </div>

  <div class="who">
    {#if ship}
      <span class="ship">{ship.model}</span>
      {#if !compact && ship.manufacturer}<span class="maker">{ship.manufacturer}</span>{/if}
      {#if status?.role}<span class="seat">{ROLE[status.role] ?? status.role}</span>{/if}
    {:else if status?.locomotion === "seated"}
      <span class="ship">Boarding…</span>
    {:else if status}
      <span class="ship muted">{status.locomotion === "eva" ? "EVA" : "On foot"}</span>
    {/if}
  </div>

  <div class="right">
    {#if ship?.master_mode}
      <span class="mode {ship.master_mode.toLowerCase()}">{ship.master_mode}</span>
    {:else if ship && ship.powered === false}
      <span class="mode off">Powered down</span>
    {/if}
    <span class="conn" class:live title={agent?.message ?? ""}>
      <span class="dot"></span>{statusText}
    </span>
    <button class="toggle" onclick={onToggleCompact} title="Compact view for VR overlays">
      {compact ? "Full" : "Compact"}
    </button>
  </div>
</header>

<style>
  .top {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 12px 18px;
    border: 1px solid var(--line);
    border-radius: var(--radius);
    background: color-mix(in srgb, var(--panel) 85%, transparent);
    backdrop-filter: blur(8px);
    position: sticky;
    top: 10px;
    z-index: 5;
    min-width: 0;
  }
  .compact.top {
    padding: 8px 12px;
    gap: 10px;
    top: 6px;
  }
  .brand {
    display: flex;
    align-items: center;
    gap: 9px;
    font-weight: 700;
    letter-spacing: 0.02em;
    flex: none;
  }
  .brand svg {
    width: 22px;
    height: 22px;
    fill: none;
    stroke: var(--accent);
    stroke-width: 3;
    stroke-linejoin: round;
  }
  .brand circle {
    fill: var(--accent);
    stroke: none;
  }
  .who {
    display: flex;
    align-items: baseline;
    gap: 10px;
    min-width: 0;
    flex: 1;
    overflow: hidden;
    white-space: nowrap;
  }
  .ship {
    font-size: 1.15rem;
    font-weight: 700;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .maker,
  .seat {
    color: var(--text-2);
    font-size: 0.9rem;
  }
  .seat::before {
    content: "·";
    margin-right: 10px;
    color: var(--text-3);
  }
  .muted {
    color: var(--text-2);
  }
  .right {
    display: flex;
    align-items: center;
    gap: 10px;
    flex: none;
  }
  .mode {
    font-family: var(--mono);
    font-weight: 800;
    letter-spacing: 0.12em;
    font-size: 0.85rem;
    padding: 5px 11px;
    border-radius: 8px;
    border: 1px solid currentColor;
  }
  .mode.scm {
    color: var(--scm);
    background: #46d3ff18;
  }
  .mode.nav {
    color: var(--nav);
    background: #a78bfa18;
  }
  .mode.off {
    color: var(--text-3);
    font-family: var(--font);
    letter-spacing: 0.04em;
  }
  .conn {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    font-size: 0.85rem;
    color: var(--text-3);
    max-width: 260px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .conn .dot {
    color: var(--warn);
  }
  .conn.live {
    color: var(--good);
  }
  .conn.live .dot {
    color: var(--good);
    box-shadow: 0 0 10px var(--good);
    animation: pulse 1.6s ease-in-out infinite;
  }
  .toggle {
    border: 1px solid var(--line-2);
    background: var(--bg-2);
    border-radius: 8px;
    padding: 5px 10px;
    font-size: 0.8rem;
    color: var(--text-2);
    cursor: pointer;
  }
  .toggle:hover {
    color: var(--text);
    border-color: var(--accent);
  }
  .toggle:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }
  @media (max-width: 640px) {
    .top {
      padding: 10px 12px;
      gap: 10px;
    }
    .brand span,
    .maker {
      display: none;
    }
    .conn {
      max-width: 90px;
    }
    .toggle {
      display: none;
    }
  }
</style>
