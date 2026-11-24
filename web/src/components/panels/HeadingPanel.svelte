<script lang="ts">
  import type { ShipCtx } from "../../lib/context";
  import HeadingTape from "../gauges/HeadingTape.svelte";

  let { ctx }: { ctx: ShipCtx } = $props();
  // The game's heading is a bearing over the planet below; with no planet
  // (altitude unknown) it isn't sent, so say why rather than "No heading".
  const f = $derived(ctx.ship.flight);
  const note = $derived(f.heading == null && f.alt == null ? "No heading in deep space" : "No heading");
</script>

<HeadingTape heading={f.heading} compact={ctx.compact} {note} />
