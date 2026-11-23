<script lang="ts">
  import type { ShipCtx } from "../../lib/context";
  import Annunciators from "../Annunciators.svelte";

  let { ctx }: { ctx: ShipCtx } = $props();
  const ship = $derived(ctx.ship);
  const gearMoving = $derived(ship.gear === "deploying" || ship.gear === "retracting");
</script>

<Annunciators lights={ship.lights} />
<div class="chips">
  <span class="chip" class:on={ship.landed} class:off={!ship.landed}>
    <span class="dot"></span>{ship.landed ? "Landed" : ship.landed === false ? "Flying" : "Landed ?"}
  </span>
  {#if ship.gear}
    <span class="chip" class:warn={gearMoving} class:pulse={gearMoving} class:on={ship.gear === "deployed"}>
      Gear {ship.gear}
    </span>
  {/if}
</div>

<style>
  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-top: 6px;
  }
  .pulse {
    animation: pulse 0.9s ease-in-out infinite;
  }
</style>
