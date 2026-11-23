<script lang="ts">
  import type { TelemetryEvent } from "../lib/types";
  import { clock, eventText, eventTone } from "../lib/format";

  let { events, limit = 12 }: { events: TelemetryEvent[]; limit?: number } = $props();
</script>

<div class="panel feed">
  <span class="label">Events</span>
  {#if events.length === 0}
    <p class="empty">Nothing yet. Events appear as you play: seats, takeoff, landing, warnings.</p>
  {:else}
    <ol>
      {#each events.slice(0, limit) as e}
        <li class={eventTone(e.kind, e.data)}>
          <span class="dot"></span>
          <span class="text">{eventText(e.kind, e.data)}</span>
          <time class="num">{clock(e.t)}</time>
        </li>
      {/each}
    </ol>
  {/if}
</div>

<style>
  ol {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 2px;
  }
  li {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 7px 4px;
    border-bottom: 1px solid var(--line);
    font-size: 0.9rem;
  }
  li:last-child {
    border-bottom: 0;
  }
  .text {
    flex: 1;
    min-width: 0;
  }
  time {
    color: var(--text-3);
    font-size: 0.78rem;
  }
  .info .dot {
    color: var(--accent);
  }
  .good .dot {
    color: var(--good);
  }
  .warn .dot {
    color: var(--warn);
  }
  .bad .dot {
    color: var(--bad);
  }
  .bad .text {
    color: #ffd0d5;
  }
  .empty {
    margin: 0;
    color: var(--text-3);
    font-size: 0.9rem;
  }
</style>
