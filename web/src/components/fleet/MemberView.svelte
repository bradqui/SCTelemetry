<script lang="ts">
  import type { PanelCtx } from "../../lib/context";
  import { ago, ROLE_NAMES } from "../../lib/format";
  import type { Prefs } from "../../lib/prefs.svelte";
  import type { Trends } from "../../lib/trends.svelte";
  import type { MemberSummary, Snapshot, TelemetryEvent } from "../../lib/types";
  import Dashboard from "../Dashboard.svelte";
  import LocationChips from "../LocationChips.svelte";

  let {
    member,
    snap,
    events,
    trends,
    prefs,
    now,
    myShard,
    isMe,
    onClose,
  }: {
    member: MemberSummary;
    snap: Snapshot | null;
    events: TelemetryEvent[];
    trends: Trends;
    prefs: Prefs;
    now: number;
    myShard: string | null;
    isMe: boolean;
    onClose: () => void;
  } = $props();

  const ship = $derived(snap?.ship ?? null);
  const ctx = $derived<PanelCtx | null>(
    snap ? { snap, ship, events, trends, prefs, compact: false, now, who: isMe ? undefined : member.name } : null,
  );
  const loc = $derived(snap?.location ?? null);
  const same = $derived(!isMe && !!myShard && loc?.shard === myShard);
  const where = $derived.by(() => {
    if (member.presence === "offline") return member.last_seen ? `Offline · seen ${ago(member.last_seen, now)}` : "Offline";
    if (member.presence === "stale") return "Connection lost";
    if (member.presence === "idle") return "Agent running · not in game";
    if (ship) return `${ship.model}${snap?.status?.role ? ` · ${ROLE_NAMES[snap.status.role]}` : ""}`;
    const l = snap?.status?.locomotion;
    return l === "eva" ? "EVA" : l === "seated" ? "Seated" : "On foot";
  });
  const mode = $derived(
    ship?.flight.quantum ? "QT" : ship?.powered === false ? null : (ship?.master_mode ?? null),
  );
</script>

<div class="member">
  <header>
    <button class="back" onclick={onClose} aria-label="Back to the fleet" title="Back to the fleet">
      <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M10 3 5 8l5 5" /></svg>
    </button>
    {#if member.avatar}<img src={member.avatar} alt="" />{/if}
    <div class="who">
      <b>{member.name}{#if isMe}<em>you</em>{/if}</b>
      <small class="p-{member.presence}">{where}</small>
    </div>
    {#if loc}<LocationChips {loc} sameServer={same} />{/if}
    {#if mode}
      <span class="mode {mode.toLowerCase()}" title={mode === "QT" && loc?.route?.destination ? `Quantum to ${loc.route.destination}` : undefined}
        >{mode}{#if mode === "QT" && loc?.route?.destination}<small>{loc.route.destination}</small>{/if}</span
      >
    {/if}
  </header>

  {#if ctx}
    <Dashboard {ctx} layout={prefs.full} />
  {:else}
    <section class="none">
      <h2>{member.presence === "offline" ? "Offline" : member.presence === "idle" ? "Not in game" : "Waiting for telemetry"}</h2>
      <p>
        {#if member.presence === "offline"}
          {member.name} isn't running the agent right now.
        {:else if member.presence === "idle"}
          {member.name}'s agent is running; their telemetry appears here once they load into the game.
        {:else}
          Their next update will show here.
        {/if}
      </p>
    </section>
  {/if}
</div>

<style>
  .member {
    display: grid;
    gap: var(--gap);
    align-content: start;
    min-width: 0;
  }
  header {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 6px 10px;
    border: 1px solid var(--line);
    border-radius: var(--radius);
    background: linear-gradient(180deg, var(--panel-2), var(--panel));
    min-width: 0;
  }
  .back {
    display: grid;
    place-items: center;
    width: 26px;
    height: 26px;
    border: 1px solid var(--line-2);
    border-radius: 2px;
    background: var(--bg-2);
    cursor: pointer;
    flex: none;
  }
  .back svg {
    width: 14px;
    height: 14px;
    fill: none;
    stroke: currentColor;
    stroke-width: 2;
  }
  .back:hover {
    border-color: var(--accent);
  }
  img {
    width: 28px;
    height: 28px;
    border-radius: 2px;
    flex: none;
  }
  .who {
    display: grid;
    min-width: 0;
    flex: 0 1 auto;
    line-height: 1.2;
  }
  .who b {
    font-size: 1.05rem;
    white-space: nowrap;
  }
  .who em {
    font-style: normal;
    font-size: 0.6rem;
    font-weight: 800;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--accent);
    border: 1px solid currentColor;
    border-radius: 2px;
    padding: 0 4px;
    margin-left: 7px;
    vertical-align: 2px;
  }
  .who small {
    color: var(--text-2);
    font-size: 0.78rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .who .p-offline,
  .who .p-stale {
    color: var(--warn);
  }
  .mode {
    margin-left: auto;
    display: inline-flex;
    align-items: center;
    gap: 7px;
    font-family: var(--mono);
    font-weight: 800;
    letter-spacing: 0.12em;
    font-size: 0.82rem;
    padding: 3px 9px;
    border-radius: 2px;
    border: 1px solid currentColor;
    flex: none;
  }
  .mode small {
    font-family: var(--font);
    letter-spacing: 0.02em;
    font-weight: 650;
    font-size: 0.74rem;
  }
  .mode.scm {
    color: var(--scm);
    background: color-mix(in srgb, var(--scm) 12%, transparent);
  }
  .mode.nav,
  .mode.qt {
    color: var(--nav);
    background: color-mix(in srgb, var(--nav) 14%, transparent);
  }
  .mode.qt {
    animation: pulse 1.2s ease-in-out infinite;
  }
  .none {
    padding: 48px 24px;
    text-align: center;
    border: 1px solid var(--line);
    border-radius: var(--radius);
    background: linear-gradient(180deg, var(--panel-2), var(--panel));
  }
  .none h2 {
    margin: 0 0 6px;
    font-size: 1.2rem;
  }
  .none p {
    margin: 0 auto;
    color: var(--text-2);
    max-width: 46ch;
  }
  @media (min-width: 761px) {
    .back {
      display: none;
    }
  }
</style>
