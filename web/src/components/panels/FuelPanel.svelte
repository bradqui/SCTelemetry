<script lang="ts">
  import type { ShipCtx } from "../../lib/context";
  import Tank from "../gauges/Tank.svelte";

  let { ctx }: { ctx: ShipCtx } = $props();
  const f = $derived(ctx.ship.flight);

  // Range: hydrogen left over how fast it's been falling this last minute. Refuelling (it
  // goes up) or a ship change starts over.
  const WINDOW_MS = 60_000;
  let samples: [number, number][] = [];
  let shipId: string | null = null;
  let range = $state<{ minutes: number } | "idle" | null>(null);
  $effect(() => {
    const t = ctx.snap.t;
    const h2 = f.h2_fuel;
    if (ctx.ship.id !== shipId || h2 == null) {
      shipId = ctx.ship.id;
      samples = [];
    }
    if (h2 == null) {
      range = null;
      return;
    }
    const last = samples[samples.length - 1];
    if (last && h2 > last[1] + 0.002) samples = []; // refuelled
    if (!last || t - last[0] >= 1000) samples.push([t, h2]);
    while (samples.length > 2 && t - samples[0][0] > WINDOW_MS) samples.shift();
    const first = samples[0];
    const span = (t - first[0]) / 1000;
    if (span < 15) {
      range = null;
      return;
    }
    const perSecond = (first[1] - h2) / span;
    range = perSecond < 0.00002 ? "idle" : { minutes: h2 / perSecond / 60 };
  });
  const rangeText = $derived(
    range == null
      ? "Range: measuring…"
      : range === "idle"
        ? "Not burning"
        : range.minutes >= 120
          ? "Range: over 2 h at this burn"
          : `Range: about ${Math.max(1, Math.round(range.minutes))} min at this burn`,
  );
</script>

<div class="tanks">
  <Tank label="Hydrogen" value={f.h2_fuel} note={ctx.ship.power.engines === false ? "Engines off" : "No data"} />
  <Tank label="Quantum" value={f.qt_fuel} note="Not sent" />
  <Tank label="Boost" value={f.boost_reserve} tone="accent" active={f.boost_engaged === true} note="No data" />
</div>
{#if f.h2_fuel != null}
  <p
    class="range"
    class:low={range != null && range !== "idle" && range.minutes < 5}
    title="How long the hydrogen lasts if you keep burning it as fast as in the last minute"
  >
    {rangeText}
  </p>
{/if}

<style>
  .tanks {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 6px;
  }
  .range {
    margin: 6px 0 0;
    font-size: 0.74rem;
    color: var(--text-2);
    text-align: center;
  }
  .range.low {
    color: var(--warn);
    font-weight: 600;
  }
  @container panel (max-width: 300px) {
    .tanks :global(.label) {
      font-size: 0.6rem;
      letter-spacing: 0.06em;
    }
  }
</style>
