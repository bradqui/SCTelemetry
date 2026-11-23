<script lang="ts">
  import type { ShipCtx } from "../../lib/context";
  import Tank from "../gauges/Tank.svelte";

  let { ctx }: { ctx: ShipCtx } = $props();
  const f = $derived(ctx.ship.flight);
</script>

<div class="tanks">
  <Tank label="Hydrogen" value={f.h2_fuel} note={ctx.ship.power.engines === false ? "Engines off" : "No data"} />
  <Tank label="Quantum" value={f.qt_fuel} note="Not sent" />
  <Tank label="Boost" value={f.boost_reserve} tone="accent" active={f.boost_engaged === true} note="No data" />
</div>

<style>
  .tanks {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 10px;
    padding-top: 4px;
  }
  @container panel (max-width: 300px) {
    .tanks :global(.label) {
      font-size: 0.6rem;
      letter-spacing: 0.06em;
    }
  }
</style>
