<script lang="ts">
  // Ship: Hull & shields and the warning lights together, beside Flight in the built-in
  // layouts. The two parts are the same as the separate panels (still in Customize).
  import type { ShipCtx } from "../../lib/context";
  import ShipPanel from "./ShipPanel.svelte";
  import WarningsPanel from "./WarningsPanel.svelte";

  let { ctx }: { ctx: ShipCtx } = $props();
</script>

<div class="status">
  <ShipPanel {ctx} />
  <div class="lights"><WarningsPanel {ctx} gear={false} /></div>
</div>

<style>
  .status {
    display: grid;
    grid-template-rows: auto minmax(0, 1fr);
    gap: 10px;
    height: 100%;
  }
  .lights {
    border-top: 1px solid var(--line);
    padding-top: 10px;
    display: grid;
    align-content: start;
  }
  /* More room than the Warnings panel alone: taller lights, easier to read. */
  .lights {
    --tile-h: 74px;
    --tile-code: 1rem;
  }
</style>
