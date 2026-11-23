<script lang="ts">
  import type { ShipCtx } from "../../lib/context";
  import HeadingTape from "../gauges/HeadingTape.svelte";

  let { ctx }: { ctx: ShipCtx } = $props();
</script>

<HeadingTape heading={ctx.ship.flight.heading} compact={ctx.compact} />
