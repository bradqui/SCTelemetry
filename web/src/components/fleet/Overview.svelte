<script lang="ts">
  import { CATEGORIES, eventCategory, eventText, eventTone, since, type EventCategory } from "../../lib/format";
  import type { FleetEvent, MemberSummary } from "../../lib/types";
  import EventIcon from "../EventIcon.svelte";

  // The fleet with nobody opened: what everyone did this session, and everything as it happens.
  let {
    roster,
    events,
    now,
    onOpen,
  }: {
    roster: Record<string, MemberSummary>;
    events: FleetEvent[];
    now: number;
    onOpen: (id: string) => void;
  } = $props();

  const rows = $derived(Object.values(roster));
  const totals = $derived.by(() => {
    const t = { kills: 0, contracts: 0, quantum: 0, earned: 0, lost: 0, downed: 0 };
    for (const m of rows) {
      const s = m.session;
      if (!s || m.presence === "offline") continue;
      t.kills += s.kills;
      t.contracts += s.contracts;
      t.quantum += s.quantum_trips;
      t.earned += s.earned;
      t.lost += s.ships_lost;
      t.downed += s.incaps + s.deaths;
    }
    return t;
  });
  const tiles = $derived([
    { label: "Kills", value: totals.kills, tone: totals.kills ? "good" : "" },
    { label: "Contracts", value: totals.contracts, tone: totals.contracts ? "good" : "" },
    { label: "Quantum trips", value: totals.quantum, tone: "" },
    {
      label: "aUEC earned",
      value: totals.earned >= 10000 ? `${Math.round(totals.earned / 1000)}k` : totals.earned.toLocaleString(),
      tone: totals.earned ? "good" : "",
    },
    { label: "Ships lost", value: totals.lost, tone: totals.lost ? "bad" : "" },
    { label: "Downed", value: totals.downed, tone: totals.downed ? "bad" : "" },
  ]);

  let filter = $state<EventCategory | "all">("all");
  const feed = $derived(
    events
      .filter((e) => e.kind !== "game_start" && (filter === "all" || eventCategory(e.kind) === filter))
      .slice(-80)
      .reverse(),
  );
  const crews = $derived.by(() => {
    const ships = new Map<string, MemberSummary[]>();
    for (const m of rows) {
      if (m.ship && m.presence !== "offline") ships.set(m.ship.id, [...(ships.get(m.ship.id) ?? []), m]);
    }
    return [...ships.values()].sort((a, b) => b.length - a.length);
  });
</script>

<div class="overview">
  <section class="tiles">
    {#each tiles as t (t.label)}
      <div class="tile {t.tone}">
        <span class="n num display">{t.value}</span>
        <span class="label">{t.label}</span>
      </div>
    {/each}
  </section>

  <section class="panel ships">
    <span class="label">Ships out</span>
    {#each crews as crew (crew[0].ship!.id)}
      {@const s = crew[0].ship!}
      <button class="ship" onclick={() => onOpen(crew[0].id)}>
        <span class="mode {s.quantum ? 'qt' : (s.master_mode ?? 'off').toLowerCase()}">{s.quantum ? "QT" : (s.master_mode ?? "—")}</span>
        <b>{s.model}</b>
        <small>{crew.map((m) => m.name).join(", ")}</small>
        {#if s.alarm}<span class="alarm {s.alarm}">!</span>{/if}
      </button>
    {:else}
      <p class="muted">Nobody is in a ship right now.</p>
    {/each}
  </section>

  <section class="panel feed">
    <div class="feed-head">
      <span class="label">Fleet activity</span>
      <div class="filters">
        <button class:on={filter === "all"} onclick={() => (filter = "all")}>All</button>
        {#each CATEGORIES.filter((c) => c.id !== "you") as c (c.id)}
          <button class:on={filter === c.id} onclick={() => (filter = c.id)}>{c.label}</button>
        {/each}
      </div>
    </div>
    <ol>
      {#each feed as e (`${e.member}-${e.t}-${e.kind}`)}
        <li class="{eventTone(e.kind, e.data)} cat-{eventCategory(e.kind)}">
          <span class="icon"><EventIcon kind={e.kind} size={13} /></span>
          <button class="name" onclick={() => onOpen(e.member)}>{roster[e.member]?.name ?? "Someone"}</button>
          <span class="text">{eventText(e.kind, e.data)}</span>
          <time class="num">{since(e.t, now)}</time>
        </li>
      {:else}
        <li class="empty">Nothing yet. Events from everyone show up here as they happen.</li>
      {/each}
    </ol>
  </section>
</div>

<style>
  .overview {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 2fr);
    grid-template-rows: auto minmax(0, 1fr);
    gap: var(--gap);
    height: 100%;
    min-height: 0;
  }
  .tiles {
    grid-column: 1 / -1;
    display: grid;
    grid-template-columns: repeat(6, minmax(0, 1fr));
    gap: 4px;
  }
  .tile {
    display: grid;
    gap: 2px;
    padding: 8px 12px;
    border: 1px solid var(--line);
    border-radius: var(--radius-sm);
    background: linear-gradient(180deg, var(--panel-2), var(--panel));
  }
  .tile .n {
    font-size: 1.5rem;
    font-weight: 800;
    line-height: 1;
  }
  .tile.good .n {
    color: var(--good);
  }
  .tile.bad .n {
    color: var(--bad);
  }
  .panel {
    padding: 10px 12px;
    display: grid;
    align-content: start;
    gap: 4px;
    min-height: 0;
    overflow-y: auto;
  }
  .ship {
    display: grid;
    grid-template-columns: 40px minmax(0, 1fr) auto;
    grid-template-rows: auto auto;
    column-gap: 8px;
    align-items: center;
    text-align: left;
    padding: 6px 8px;
    border: 1px solid var(--line);
    border-radius: var(--radius-sm);
    background: var(--bg-2);
    cursor: pointer;
  }
  .ship:hover {
    border-color: var(--accent);
  }
  .ship .mode {
    grid-row: span 2;
  }
  .ship b {
    font-size: 0.86rem;
  }
  .ship small {
    grid-column: 2;
    color: var(--text-2);
    font-size: 0.74rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .ship .alarm {
    grid-row: 1 / span 2;
    grid-column: 3;
  }
  .mode,
  .alarm {
    display: inline-grid;
    place-items: center;
    height: 20px;
    border-radius: var(--radius-sm);
    border: 1px solid currentColor;
    font-family: var(--mono);
    font-size: 0.62rem;
    font-weight: 800;
    letter-spacing: 0.06em;
  }
  .mode.scm {
    color: var(--scm);
  }
  .mode.nav,
  .mode.qt {
    color: var(--nav);
  }
  .mode.off {
    color: var(--text-3);
  }
  .alarm {
    width: 20px;
  }
  .alarm.minor {
    background: var(--warn);
    color: var(--bg);
    border-color: var(--warn);
  }
  .alarm.major {
    background: var(--bad);
    color: #fff;
    border-color: var(--bad);
  }
  .feed {
    grid-template-rows: auto minmax(0, 1fr);
    overflow: hidden;
  }
  .feed-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }
  .filters {
    display: flex;
    gap: 3px;
  }
  .filters button {
    border: 1px solid var(--line-2);
    background: var(--bg-2);
    color: var(--text-3);
    border-radius: var(--radius-sm);
    font-size: 0.62rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    padding: 2px 7px;
    cursor: pointer;
  }
  .filters button.on {
    color: var(--accent);
    border-color: var(--accent);
  }
  ol {
    list-style: none;
    margin: 6px 0 0;
    padding: 0;
    overflow-y: auto;
    min-height: 0;
  }
  li {
    display: grid;
    grid-template-columns: 18px auto minmax(0, 1fr) auto;
    align-items: center;
    gap: 7px;
    padding: 4px 6px;
    border-left: 2px solid var(--rail, var(--line-2));
    font-size: 0.82rem;
  }
  li + li {
    margin-top: 2px;
  }
  li.cat-flight {
    --rail: var(--accent);
  }
  li.cat-combat {
    --rail: var(--bad);
  }
  li.cat-mission {
    --rail: var(--warn);
  }
  li.cat-location {
    --rail: var(--nav);
  }
  li.cat-you {
    --rail: var(--good);
  }
  .icon {
    color: var(--text-2);
  }
  li.good .icon {
    color: var(--good);
  }
  li.warn .icon {
    color: var(--warn);
  }
  li.bad .icon {
    color: var(--bad);
  }
  .name {
    border: 0;
    background: none;
    padding: 0;
    font-weight: 700;
    cursor: pointer;
    white-space: nowrap;
  }
  .name:hover {
    color: var(--accent);
  }
  .text {
    color: var(--text-2);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  time {
    color: var(--text-3);
    font-size: 0.72rem;
  }
  .muted,
  .empty {
    color: var(--text-3);
    font-size: 0.85rem;
  }
  li.empty {
    display: block;
    border: 0;
  }
  @media (max-width: 1100px) {
    .overview {
      grid-template-columns: minmax(0, 1fr);
      grid-template-rows: auto auto minmax(0, 1fr);
    }
    .tiles {
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }
  }
</style>
