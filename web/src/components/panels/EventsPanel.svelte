<script lang="ts">
  import { fly } from "svelte/transition";
  import type { PanelCtx } from "../../lib/context";
  import { CATEGORIES, clock, eventCategory, eventText, eventTone, since, type EventCategory } from "../../lib/format";
  import EventIcon from "../EventIcon.svelte";

  // The Activity panel: session counts, the latest thing that happened, and a
  // filterable timeline coloured by category.
  let { ctx }: { ctx: PanelCtx } = $props();

  let filter = $state<EventCategory | "all">("all");
  const session = $derived(ctx.snap.session ?? null);
  const events = $derived(ctx.events.filter((e) => e.kind !== "game_start"));
  const latest = $derived(events[0] ?? null);
  const shown = $derived(
    (filter === "all" ? events.slice(1) : events.filter((e) => eventCategory(e.kind) === filter)).slice(0, 30),
  );
  const counts = $derived.by(() => {
    const c: Record<string, number> = {};
    for (const e of events) c[eventCategory(e.kind)] = (c[eventCategory(e.kind)] ?? 0) + 1;
    return c;
  });

  const stats = $derived(
    session
      ? [
          { label: "Kills", value: session.kills, tone: session.kills ? "good" : "" },
          { label: "Contracts", value: session.contracts, tone: session.contracts ? "good" : "" },
          { label: "Quantum", value: session.quantum_trips, tone: "" },
          ...(session.system_jumps ? [{ label: "Jumps", value: session.system_jumps, tone: "" }] : []),
          {
            label: "aUEC",
            value: session.earned >= 10000 ? `${Math.round(session.earned / 1000)}k` : session.earned.toLocaleString(),
            tone: session.earned ? "good" : "",
          },
          ...(session.ships_lost ? [{ label: "Ships lost", value: session.ships_lost, tone: "bad" }] : []),
          ...(session.incaps + session.deaths
            ? [{ label: "Downed", value: session.incaps + session.deaths, tone: "bad" }]
            : []),
        ]
      : [],
  );
</script>

<div class="activity">
  {#if stats.length}
    <div class="stats">
      {#each stats as s (s.label)}
        <div class="stat {s.tone}">
          <span class="n num">{s.value}</span>
          <span class="label">{s.label}</span>
        </div>
      {/each}
    </div>
  {/if}

  {#if latest}
    {#key latest}
      <div class="latest {eventTone(latest.kind, latest.data)}" in:fly={{ y: -10, duration: 280 }}>
        <span class="big-icon"><EventIcon kind={latest.kind} size={20} /></span>
        <div class="what">
          <span class="text">{eventText(latest.kind, latest.data)}</span>
          <span class="meta">
            {CATEGORIES.find((c) => c.id === eventCategory(latest.kind))?.label} · {since(latest.t, ctx.now)}
          </span>
        </div>
      </div>
    {/key}

    <div class="filters" role="tablist" aria-label="Filter activity">
      <button class:on={filter === "all"} onclick={() => (filter = "all")} role="tab" aria-selected={filter === "all"}>
        All
      </button>
      {#each CATEGORIES as c (c.id)}
        <button
          class="f-{c.id}"
          class:on={filter === c.id}
          disabled={!counts[c.id]}
          onclick={() => (filter = filter === c.id ? "all" : c.id)}
          role="tab"
          aria-selected={filter === c.id}
        >
          {c.label}{#if counts[c.id]}<b class="num">{counts[c.id]}</b>{/if}
        </button>
      {/each}
    </div>

    <ol>
      {#each shown as e (`${e.t}-${e.kind}-${JSON.stringify(e.data)}`)}
        <li class="c-{eventCategory(e.kind)} {eventTone(e.kind, e.data)}" in:fly={{ y: -6, duration: 220 }}>
          <span class="icon"><EventIcon kind={e.kind} size={12} /></span>
          <span class="text">{eventText(e.kind, e.data)}</span>
          <time class="num" title={clock(e.t)}>{since(e.t, ctx.now)}</time>
        </li>
      {:else}
        <li class="none">Nothing else {filter === "all" ? "yet" : "in this category"}.</li>
      {/each}
    </ol>
  {:else}
    <p class="empty">
      Nothing yet. Contracts, kills, zones, quantum jumps, seats, takeoff and warnings show up here as they happen.
    </p>
  {/if}
</div>

<style>
  .activity {
    display: grid;
    gap: 6px;
    --flight: var(--accent);
    --combat: var(--bad);
    --mission: #f5c26b;
    --location: var(--nav);
    --you: var(--good);
  }
  .stats {
    display: flex;
    gap: 3px;
  }
  .stat {
    flex: 1;
    min-width: 0;
    display: grid;
    justify-items: center;
    padding: 3px 4px;
    border: 1px solid var(--line);
    background: var(--bg-2);
    border-radius: 2px;
  }
  .stat .n {
    font-size: 1.05rem;
    font-weight: 750;
    line-height: 1.15;
  }
  .stat.good .n {
    color: var(--good);
  }
  .stat.bad .n {
    color: var(--bad);
  }
  .stat .label {
    font-size: 0.56rem;
    white-space: nowrap;
  }

  .latest {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 7px 10px;
    border-radius: 2px;
    border: 1px solid color-mix(in srgb, var(--c) 45%, transparent);
    background: linear-gradient(90deg, color-mix(in srgb, var(--c) 16%, var(--bg-2)), var(--bg-2));
    box-shadow: 0 0 var(--glow, 0px) color-mix(in srgb, var(--c) 30%, transparent);
    --c: var(--accent);
  }
  .latest.good {
    --c: var(--good);
  }
  .latest.warn {
    --c: var(--warn);
  }
  .latest.bad {
    --c: var(--bad);
  }
  .big-icon {
    width: 34px;
    height: 34px;
    display: grid;
    place-items: center;
    flex: none;
    color: var(--c);
    border: 1px solid var(--c);
    border-radius: 2px;
    background: color-mix(in srgb, var(--c) 14%, transparent);
  }
  .what {
    display: grid;
    min-width: 0;
  }
  .latest .text {
    font-size: 0.98rem;
    font-weight: 700;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .meta {
    font-size: 0.68rem;
    color: var(--text-3);
    letter-spacing: 0.04em;
  }

  .filters {
    display: flex;
    flex-wrap: wrap;
    gap: 3px;
  }
  .filters button {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 7px;
    border-radius: 2px;
    border: 1px solid var(--line-2);
    background: var(--bg-2);
    color: var(--text-3);
    font-size: 0.64rem;
    font-weight: 700;
    letter-spacing: 0.07em;
    text-transform: uppercase;
    cursor: pointer;
  }
  .filters button b {
    font-weight: 600;
    color: var(--text-2);
  }
  .filters button.on {
    color: var(--text);
    border-color: var(--accent);
    background: color-mix(in srgb, var(--accent) 18%, var(--bg-2));
  }
  .filters button:disabled {
    opacity: 0.4;
    cursor: default;
  }
  .filters button:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 1px;
  }

  ol {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 2px;
    max-height: 150px;
    overflow-y: auto;
    scrollbar-width: thin;
  }
  li {
    display: flex;
    align-items: center;
    gap: 7px;
    padding: 2px 6px 2px 5px;
    border-left: 2px solid var(--cat);
    background: color-mix(in srgb, var(--cat) 5%, transparent);
    font-size: 0.78rem;
    --cat: var(--flight);
  }
  .c-combat {
    --cat: var(--combat);
  }
  .c-mission {
    --cat: var(--mission);
  }
  .c-location {
    --cat: var(--location);
  }
  .c-you {
    --cat: var(--you);
  }
  .icon {
    color: var(--cat);
    display: grid;
    place-items: center;
  }
  li .text {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  li.bad .text {
    color: #ffd0d5;
  }
  time {
    color: var(--text-3);
    font-size: 0.7rem;
  }
  li.none {
    border-left-color: var(--line);
    color: var(--text-3);
    background: none;
  }
  .empty {
    margin: 0;
    color: var(--text-3);
    font-size: 0.85rem;
  }
</style>
