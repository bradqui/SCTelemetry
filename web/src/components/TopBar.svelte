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
    replay = false,
    caution = true,
    onToggleCompact,
    onCustomize,
  }: {
    socket: "connecting" | "open" | "closed";
    agent: AgentState | null;
    snapshot: Snapshot | null;
    compact: boolean;
    replay?: boolean;
    /** Show the master caution/warning in the bar. */
    caution?: boolean;
    onToggleCompact: () => void;
    onCustomize: () => void;
  } = $props();

  const live = $derived(socket === "open" && agent?.streaming);
  const statusText = $derived(
    socket !== "open"
      ? "Agent offline"
      : agent?.streaming
        ? replay
          ? "Replay"
          : "Live"
        : (agent?.message ?? "Connecting"),
  );
  const ship = $derived(snapshot?.ship ?? null);
  const status = $derived(snapshot?.status ?? null);

  const LIGHT_NAMES: Record<string, string> = {
    pwr: "Power",
    wpn: "Weapons",
    thr: "Thrusters",
    shld: "Shields",
    cool: "Cooling",
    qdrv: "Quantum drive",
    radr: "Radar",
    prox: "Proximity",
    hit: "Taking hits",
    misl: "Missile lock",
  };
  const alarm = $derived.by(() => {
    if (!caution || !ship) return null;
    const lit = (prefix: string) =>
      Object.entries(ship.lights)
        .filter(([, l]) => l?.startsWith(prefix))
        .map(([k]) => LIGHT_NAMES[k] ?? k.toUpperCase());
    const major = lit("major");
    if (major.length) return { level: "warning", text: major.join(" · ") };
    const minor = lit("minor");
    return minor.length ? { level: "caution", text: minor.join(" · ") } : null;
  });
</script>

<header class="top {alarm ? `alarm-${alarm.level}` : ''}" class:compact>
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

  {#if alarm}
    <div class="alarm {alarm.level}" role="alert">
      <span class="tag">{alarm.level === "warning" ? "Warning" : "Caution"}</span>
      <span class="what">{alarm.text}</span>
    </div>
  {/if}

  <div class="right">
    {#if ship?.flight.quantum}
      <span class="mode qt">QT</span>
    {:else if ship?.master_mode}
      <span class="mode {ship.master_mode.toLowerCase()}">{ship.master_mode}</span>
    {:else if ship && ship.powered === false}
      <span class="mode off">Powered down</span>
    {/if}
    <span class="conn" class:live title={agent?.message ?? ""}>
      <span class="dot"></span>{statusText}
    </span>
    <button class="toggle compact-toggle" onclick={onToggleCompact} title="Compact view for VR overlays">
      {compact ? "Full" : "Compact"}
    </button>
    <button class="toggle icon" onclick={onCustomize} title="Customize the layout" aria-label="Customize">
      <svg viewBox="0 0 16 16" aria-hidden="true"
        ><path
          d="M2 4h7M13 4h1M2 12h1M7 12h7M11 2.5v3M5 10.5v3M2 8h3M9 8h5M7 6.5v3"
        /></svg
      >
    </button>
  </div>
</header>

<style>
  .top {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 5px 12px;
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
  .toggle.icon {
    display: grid;
    place-items: center;
    padding: 4px 7px;
  }
  .toggle.icon svg {
    width: 16px;
    height: 16px;
    fill: none;
    stroke: currentColor;
    stroke-width: 1.6;
    stroke-linecap: round;
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
    .top:not(.compact) .compact-toggle {
      display: none;
    }
  }
  .alarm {
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
    flex: 0 1 auto;
    overflow: hidden;
    font-size: 0.82rem;
    font-weight: 650;
  }
  .tag {
    flex: none;
    font-family: var(--mono);
    font-size: 0.7rem;
    font-weight: 800;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    padding: 2px 7px;
    border-radius: 2px;
  }
  .what {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .alarm.caution {
    color: var(--warn);
  }
  .alarm.caution .tag {
    background: var(--warn);
    color: var(--bg);
  }
  .alarm.warning {
    color: #ffd6da;
  }
  .alarm.warning .tag {
    background: var(--bad);
    color: #fff;
    animation: flash 0.8s steps(1) infinite;
  }
  .top.alarm-caution {
    border-color: var(--warn);
    box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--warn) 40%, transparent);
  }
  .top.alarm-warning {
    border-color: var(--bad);
    animation: alarm 1s steps(1) infinite;
  }
  @keyframes alarm {
    50% {
      background: color-mix(in srgb, var(--bad) 22%, var(--panel));
    }
  }
  .mode.qt {
    color: var(--nav);
    background: #a78bfa28;
    animation: pulse 1.2s ease-in-out infinite;
  }
  @media (max-width: 640px) {
    .what {
      display: none;
    }
  }
</style>
