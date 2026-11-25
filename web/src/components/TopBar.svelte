<script lang="ts">
  import { alertLights, chosen, defaultAlerts, type AlertPick } from "../lib/alerts";
  import { LIGHT_NAMES, placeText, ROLE_NAMES as ROLE } from "../lib/format";
  import { openOnHub } from "../lib/hub";
  import { markNow, openReport } from "../lib/reports";
  import { view } from "../lib/remote.svelte";
  import WindowButtons from "./WindowButtons.svelte";
  import LocationChips from "./LocationChips.svelte";
  import type { AgentState, ReportsStatus, Snapshot, UpdaterStatus, UplinkStatus } from "../lib/types";

  let {
    socket,
    agent,
    snapshot,
    compact,
    replay = false,
    alerts = defaultAlerts().self,
    uplinks = [],
    updater = null,
    reports = null,
    onFleet,
    onToggleCompact,
    onCustomize,
  }: {
    socket: "connecting" | "open" | "closed";
    agent: AgentState | null;
    snapshot: Snapshot | null;
    compact: boolean;
    replay?: boolean;
    /** Which lights the master warning/caution shows (Customize → Header alerts). */
    alerts?: AlertPick;
    /** Sending to the fleet hub? */
    /** Each fleet's link (one per org's hub you're in). */
    uplinks?: UplinkStatus[];
    /** The app updating itself (selfupdate.py): one click instead of a download. */
    updater?: UpdaterStatus | null;
    /** Problem reports: the mark button, and how many moments are marked. */
    reports?: ReportsStatus | null;
    /** Show the fleet in this page (else the chip opens the hub's page). */
    onFleet?: () => void;
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
  const loc = $derived(snapshot?.location ?? null);
  const place = $derived(
    placeText(loc, { locomotion: status?.locomotion, landed: ship?.landed, quantum: ship?.flight.quantum }),
  );

  // The Fleet chip: every fleet this PC sends to. Its colour is the worst of them.
  const links = $derived(uplinks.filter((u) => u.state !== "unlinked"));
  const fleetState = $derived(
    links.some((u) => u.state === "rejected")
      ? "rejected"
      : links.every((u) => u.state === "connected")
        ? "connected"
        : "connecting",
  );
  const fleetTitle = $derived(
    links
      .map((u) => {
        const name = u.org || u.hub;
        if (u.state === "connected") return `${name}: sending${u.member ? ` as ${u.member}` : ""}`;
        return `${name}: ${u.message ?? (u.state === "rejected" ? "refused" : "connecting")}`;
      })
      .join("\n") + "\nClick to see the fleet.",
  );
  const update = $derived(links.find((u) => u.update)?.update ?? null);
  // The packaged app updates itself in one click; from source, the releases page.
  const updating = $derived(updater && ["downloading", "checking", "installing"].includes(updater.state));
  const updateLabel = $derived.by(() => {
    if (!updater || !update) return "";
    if (updater.state === "downloading") return `Updating ${Math.round((updater.progress ?? 0) * 100)}%`;
    if (updater.state === "checking") return "Checking…";
    if (updater.state === "installing") return "Restarting…";
    if (updater.state === "error") return "Update failed";
    return `Update ${updater.available ?? update.version}`;
  });
  async function updateNow() {
    await fetch("/api/agent/update", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" }).catch(
      () => {},
    );
  }
  // Marking a moment for a problem report (docs/REPORTS.md): the flag marks; once something
  // is marked, a chip says so and opens the report. A new mark makes it pulse for a moment.
  // A paired device can mark too; the report is then made on the PC.
  const canMark = $derived(!!reports?.available && reports.keep && !replay);
  const marked = $derived(reports?.marks.length ?? 0);
  let fresh = $state(false);
  let lastMark: string | null = null;
  $effect(() => {
    const newest = reports?.marks.reduce<string | null>((a, m) => (a && a > m.id ? a : m.id), null) ?? null;
    if (newest && lastMark !== null && newest !== lastMark) {
      fresh = true;
      setTimeout(() => (fresh = false), 2500);
    }
    lastMark = newest ?? "";
  });
  let markError = $state("");
  async function mark() {
    markError = "";
    await markNow().catch((e: Error) => (markError = e.message));
  }

  // The ship you're aboard on foot (its comms channel): yours, or someone else's.
  const aboard = $derived.by(() => {
    const a = loc?.aboard;
    if (!a) return null;
    const mine = !!status?.handle && a.owner.toLowerCase() === status.handle.toLowerCase();
    return mine ? `your ${a.ship}` : `${a.owner}'s ${a.ship}`;
  });


  const alarm = $derived.by(() => {
    if (!ship) return null;
    // THR in NAV is the quantum drive locking the thrusters, not a fault (alertLights).
    const { warning, caution } = chosen(alertLights(ship.lights, ship.master_mode), alerts);
    const names = (ls: string[]) => ls.map((k) => LIGHT_NAMES[k] ?? k.toUpperCase()).join(" · ");
    if (warning.length) return { level: "warning", text: names(warning) };
    return caution.length ? { level: "caution", text: names(caution) } : null;
  });
</script>

<header class="top topbar pywebview-drag-region {alarm ? `alarm-${alarm.level}` : ''}" class:compact>
  <div class="brand pywebview-drag-region">
    <svg viewBox="0 0 32 32" aria-hidden="true"><path d="M16 3 29 27H3z" /><circle cx="16" cy="20" r="3" /></svg>
    {#if !compact}<span>Starglance</span>{/if}
  </div>

  <div class="who">
    {#if ship}
      <span class="ship display">{ship.model}</span>
      {#if !compact && ship.manufacturer}<span class="maker">{ship.manufacturer}</span>{/if}
      {#if status?.role}<span class="seat">{ROLE[status.role] ?? status.role}</span>{/if}
    {:else if status?.locomotion === "seated"}
      <span class="ship">Boarding…</span>
    {:else if status}
      <span class="ship muted"
        >{status.locomotion === "eva" ? "EVA" : "On foot"}{#if aboard}<span class="aboard"> · aboard {aboard}</span>{/if}</span
      >
    {/if}
  </div>

  {#if loc}
    <LocationChips {loc} {place} />
  {/if}

  {#if alarm}
    <div class="alarm {alarm.level}" role="alert">
      <span class="tag">{alarm.level === "warning" ? "Warning" : "Caution"}</span>
      <span class="what">{alarm.text}</span>
    </div>
  {/if}

  <div class="right">
    {#if ship?.flight.quantum}
      <span class="mode qt" title={snapshot?.location?.route?.destination ? `Quantum to ${snapshot.location.route.destination}` : "Quantum travel"}>QT</span>
    {:else if ship?.master_mode}
      <span class="mode {ship.master_mode.toLowerCase()}">{ship.master_mode}</span>
    {:else if ship && ship.powered === false}
      <span class="mode off">Powered down</span>
    {/if}
    {#if links.length}
      <button class="fleet {fleetState}" onclick={() => (onFleet ? onFleet() : openOnHub())} title={fleetTitle}
        ><span class="dot"></span>{links.length > 1 ? `Fleets ×${links.length}` : "Fleet"}</button
      >
      {#if update && view.remote}
        <!-- Another device: updating is the PC's business. -->
      {:else if update && updater?.can}
        <button
          class="fleet update"
          class:busy={updating}
          disabled={!!updating}
          onclick={updateNow}
          title={updater.state === "error"
            ? `${updater.error ?? "The update failed."} Click to try again.`
            : `Starglance ${updater.available ?? update.version} is out. Click to update: it downloads the official release, checks it, and restarts in a few seconds. Your settings stay.`}
          >{updateLabel}</button
        >
      {:else if update}
        <a
          class="fleet update"
          href={update.url}
          target="_blank"
          rel="noopener noreferrer"
          title="Agent {update.version} is out. Download it from the project's releases page."
          >Update {update.version}</a
        >
      {/if}
    {/if}
    {#if canMark}
      {#if marked && view.remote}
        <span
          class="fleet marked"
          class:fresh
          title="Moments marked for a problem report, kept on the PC for a day. Report one on the PC: click this there, or Report a problem in the tray menu."
          >⚑ {marked} marked</span
        >
      {:else if marked}
        <button
          class="fleet marked"
          class:fresh
          onclick={openReport}
          title="Moments marked for a problem report, kept for a day. Click to report one.">⚑ {marked} marked</button
        >
      {/if}
      <button
        class="toggle icon"
        onclick={mark}
        title={markError ||
          `Mark this moment for a problem report${reports?.hotkey_on && reports.hotkey ? ` (or ${reports.hotkeys.find((h) => h.id === reports?.hotkey)?.label ?? reports.hotkey} in game)` : ""}`}
        aria-label="Mark this moment"
      >
        <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3.5 14.5V2 M3.5 2.5h9l-2 3 2 3h-9" /></svg>
      </button>
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
    <WindowButtons />
  </div>
</header>

<style>
  .top {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 5px 12px;
    border: var(--border-w) solid var(--line);
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
    border-radius: var(--radius-chip);
    border: 1px solid currentColor;
  }
  .mode.scm {
    color: var(--scm);
    background: color-mix(in srgb, var(--scm) 10%, transparent);
  }
  .mode.nav {
    color: var(--nav);
    background: color-mix(in srgb, var(--nav) 10%, transparent);
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
  .fleet {
    background: none;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 0.68rem;
    font-weight: 800;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    padding: 2px 7px;
    border: 1px solid currentColor;
    border-radius: var(--radius-sm);
    color: var(--text-3);
  }
  .fleet.connected {
    color: var(--good);
  }
  .fleet.offline,
  .fleet.connecting {
    color: var(--warn);
  }
  .fleet.rejected {
    color: var(--bad);
  }
  .fleet.update {
    color: var(--accent);
    text-decoration: none;
  }
  .fleet.marked {
    color: var(--warn);
  }
  .fleet.marked.fresh {
    animation: pulse 0.8s ease-in-out 3;
    background: color-mix(in srgb, var(--warn) 18%, transparent);
  }
  .fleet.update.busy {
    cursor: progress;
    opacity: 0.85;
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
    border-radius: var(--radius-sm);
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
    border-radius: var(--radius-sm);
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
    color: color-mix(in srgb, var(--bad) 35%, var(--text));
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
    background: color-mix(in srgb, var(--nav) 16%, transparent);
    animation: pulse 1.2s ease-in-out infinite;
  }
  @media (max-width: 640px) {
    .what {
      display: none;
    }
  }
  /* The title bar's job when it's hidden: drag by the bar or the logo, not their text. */
  .brand > :global(*) {
    pointer-events: none;
  }
</style>
