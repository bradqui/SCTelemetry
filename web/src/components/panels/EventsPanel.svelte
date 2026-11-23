<script lang="ts">
  import { fly } from "svelte/transition";
  import type { PanelCtx } from "../../lib/context";
  import { clock, eventText, eventTone, since } from "../../lib/format";
  import EventIcon from "../EventIcon.svelte";

  let { ctx, limit = 14 }: { ctx: PanelCtx; limit?: number } = $props();
  const shown = $derived(ctx.events.slice(0, limit));
</script>

{#if shown.length === 0}
  <p class="empty">Nothing yet. Seats, takeoff, landing, mode changes and warnings show up here.</p>
{:else}
  <ol>
    {#each shown as e (`${e.t}-${e.kind}-${JSON.stringify(e.data)}`)}
      <li class={eventTone(e.kind, e.data)} in:fly={{ y: -8, duration: 250 }}>
        <span class="icon"><EventIcon kind={e.kind} size={12} /></span>
        <span class="text">{eventText(e.kind, e.data)}</span>
        <time class="num" title={clock(e.t)}>{since(e.t, ctx.now)}</time>
      </li>
    {/each}
  </ol>
{/if}

<style>
  ol {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 0;
    max-height: 190px;
    overflow-y: auto;
    scrollbar-width: thin;
  }
  li {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 3px 2px;
    border-bottom: 1px solid var(--line);
    font-size: 0.8rem;
    --c: var(--accent);
  }
  li:last-child {
    border-bottom: 0;
  }
  .good {
    --c: var(--good);
  }
  .warn {
    --c: var(--warn);
  }
  .bad {
    --c: var(--bad);
  }
  .icon {
    width: 18px;
    height: 18px;
    flex: none;
    display: grid;
    place-items: center;
    border-radius: 2px;
    color: var(--c);
    background: color-mix(in srgb, var(--c) 14%, transparent);
  }
  .text {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .bad .text {
    color: #ffd0d5;
  }
  time {
    color: var(--text-3);
    font-size: 0.75rem;
  }
  .empty {
    margin: 0;
    color: var(--text-3);
    font-size: 0.88rem;
  }
</style>
