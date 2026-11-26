<script lang="ts">
  import { currentObjective, objectiveCount } from "../../lib/missions";
  import { showing } from "../../lib/panels";
  import { fly } from "svelte/transition";
  import type { PanelCtx } from "../../lib/context";
  import {
    auec,
    CATEGORIES,
    clock,
    eventCategory,
    eventText,
    eventTone,
    destroyedShown,
    since,
    type EventCategory,
  } from "../../lib/format";
  import EventIcon from "../EventIcon.svelte";

  // The Activity panel: session counts, the latest thing that happened, and a
  // filterable timeline coloured by category.
  let { ctx }: { ctx: PanelCtx } = $props();

  let filter = $state<EventCategory | "all">("all");
  // On the fleet page, "You" means the member being shown.
  const label = (id: EventCategory) =>
    id === "you" && ctx.who ? ctx.who : (CATEGORIES.find((c) => c.id === id)?.label ?? id);
  const session = $derived(ctx.snap.session ?? null);
  const events = $derived(
    ctx.events.filter((e) => e.kind !== "game_start" && destroyedShown(e.kind, e.data, ctx.prefs.destroyed)),
  );
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
          // Your wallet, with what this session brought in beside the label; without a
          // balance (not shared, or not in the stream), what was earned, as before.
          ctx.snap.uec != null
            ? {
                label: "Wallet",
                value: auec(ctx.snap.uec),
                tone: "",
                plus: session.earned ? `+${auec(session.earned)}` : "",
                title:
                  `Wallet: ${ctx.snap.uec.toLocaleString()} aUEC` +
                  (session.earned ? ` · earned this session: ${session.earned.toLocaleString()} aUEC` : ""),
              }
            : { label: "aUEC earned", value: auec(session.earned), tone: session.earned ? "good" : "" },
          ...(session.ships_lost ? [{ label: "Ships lost", value: session.ships_lost, tone: "bad" }] : []),
          ...(session.incaps + session.deaths
            ? [{ label: "Downed", value: session.incaps + session.deaths, tone: "bad" }]
            : []),
        ]
      : [],
  );

  // The Contract panel isn't on screen: show an active (or just-ended) contract here.
  const pinned = $derived(
    !showing(ctx.prefs, ctx.compact, "mission") ? (ctx.snap.missions?.[0] ?? null) : null,
  );
  const pinnedObjective = $derived(pinned ? currentObjective(pinned) : null);
  const pinnedCount = $derived(pinned ? objectiveCount(pinned) : null);
</script>

<div class="activity">
  <div class="left">
  {#if pinned}
    <div class="pinned {pinned.state}" title={pinned.title ?? "Contract"}>
      <span class="badge">{pinned.state === "active" ? "Contract" : pinned.state}</span>
      <span class="ptitle">{pinned.title ?? "Objective"}</span>
      {#if pinnedObjective}
        <span class="pobj" class:done={pinnedObjective.state === "complete"}
          >{pinnedObjective.state === "complete" ? "✓" : "▢"} {pinnedObjective.text}</span
        >
      {/if}
      {#if pinnedCount && pinnedCount.total > 1}<span class="pcount num">{pinnedCount.done}/{pinnedCount.total}</span>{/if}
      {#if (ctx.snap.missions?.length ?? 0) > 1}<span class="more">+{(ctx.snap.missions?.length ?? 1) - 1}</span>{/if}
    </div>
  {/if}
  {#if stats.length}
    <div class="stats">
      {#each stats as s (s.label)}
        <div class="stat {s.tone}" title={"title" in s ? s.title : undefined}>
          <span class="n num display">{s.value}</span>
          <span class="label"
            >{s.label}{#if "plus" in s && s.plus}<span class="sep">·</span><b class="plus num">{s.plus}</b><span class="sess">session</span>{/if}</span
          >
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
            {label(eventCategory(latest.kind))} · {since(latest.t, ctx.now)}
          </span>
        </div>
      </div>
    {/key}
  {/if}
  </div>
  {#if latest}
  <div class="right">
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
          {label(c.id)}{#if counts[c.id]}<b class="num">{counts[c.id]}</b>{/if}
        </button>
      {/each}
    </div>

    <ol>
      {#each shown as e (`${e.t}-${e.kind}-${JSON.stringify(e.data)}`)}
        <li
          class="c-{eventCategory(e.kind)} {eventTone(e.kind, e.data)}"
          class:nearby={e.kind === "vehicle_destroyed"}
          in:fly={{ y: -6, duration: 220 }}
        >
          <span class="icon"><EventIcon kind={e.kind} size={12} /></span>
          <span class="text">{eventText(e.kind, e.data)}</span>
          <time class="num" title={clock(e.t)}>{since(e.t, ctx.now)}</time>
        </li>
      {:else}
        <li class="none">Nothing else {filter === "all" ? "yet" : "in this category"}.</li>
      {/each}
    </ol>
  </div>
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
    --mission: var(--warn);
    --location: var(--nav);
    --you: var(--good);
  }
  .stats {
    display: flex;
    gap: 3px;
  }
  .stat {
    container-type: inline-size; /* the wallet's label shortens when its tile is narrow */
    flex: 1;
    min-width: 0;
    display: grid;
    justify-items: center;
    padding: 3px 4px;
    border: 1px solid var(--line);
    background: var(--bg-2);
    border-radius: var(--radius-sm);
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
  .stat .plus {
    color: var(--good);
    letter-spacing: 0.02em;
    text-transform: none; /* 45.2k, not 45.2K */
  }
  .stat .sep {
    margin: 0 5px;
    color: var(--text-3);
  }
  .stat .sess {
    margin-left: 4px;
  }
  /* A narrow tile: "WALLET" over "+45.2k" (the tooltip says the rest). */
  @container (max-width: 170px) {
    .stat .sess,
    .stat .sep {
      display: none;
    }
    .stat .plus {
      display: block;
      line-height: 1.2;
      text-align: center;
    }
  }

  .latest {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 7px 10px;
    border-radius: var(--radius-sm);
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
    border-radius: var(--radius-sm);
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
    border-radius: var(--radius-sm);
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
    max-height: 78px; /* three rows (it scrolls): keeps the dashboard on one 1080p screen */
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
    color: color-mix(in srgb, var(--bad) 35%, var(--text));
  }
  time {
    color: var(--text-3);
    font-size: 0.7rem;
  }
  /* Ships destroyed nearby, by someone else: context, not your news. */
  li.nearby {
    font-size: 0.72rem;
    opacity: 0.75;
    --cat: var(--line-2);
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
  .pinned {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    grid-template-areas: "badge title more" "obj obj pcount";
    gap: 2px 8px;
    align-items: baseline;
    margin-bottom: 8px;
    padding: 5px 9px;
    border-radius: var(--radius-sm);
    border-left: 3px solid var(--accent);
    background: color-mix(in srgb, var(--accent) 8%, transparent);
  }
  .pinned .badge {
    grid-area: badge;
    font-size: 0.6rem;
    font-weight: 750;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--accent);
  }
  .pinned.complete .badge {
    color: var(--good);
  }
  .pinned.failed .badge,
  .pinned.abandoned .badge {
    color: var(--bad);
  }
  .ptitle {
    grid-area: title;
    font-weight: 650;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .pcount {
    grid-area: pcount;
    font-size: 0.72rem;
    font-weight: 700;
    color: var(--text-2);
  }
  .pobj {
    grid-area: obj;
    font-size: 0.78rem;
    color: var(--text-2);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .pobj.done {
    color: var(--good);
  }
  .more {
    grid-area: more;
    font-size: 0.7rem;
    color: var(--text-3);
  }
  .left,
  .right {
    display: grid;
    gap: inherit;
    align-content: start;
    min-width: 0;
  }
  /* Wide: the contract, counts and latest event on the left; filters and the list right. */
  @container panel (min-width: 760px) {
    .activity:has(.right) {
      grid-template-columns: minmax(0, 1fr) minmax(0, 1.1fr);
      align-items: start;
      column-gap: 14px;
    }
    .right ol {
      max-height: 132px;
    }
  }
</style>
