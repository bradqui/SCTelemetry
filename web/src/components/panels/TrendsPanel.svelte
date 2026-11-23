<script lang="ts">
  import type { PanelCtx } from "../../lib/context";
  import { speed } from "../../lib/format";
  import Sparkline from "../gauges/Sparkline.svelte";

  let { ctx }: { ctx: PanelCtx } = $props();
  const kmh = $derived(ctx.prefs.speedUnit === "kmh");
  const fmtAlt = (v: number) => (Math.abs(v) >= 10_000 ? `${(v / 1000).toFixed(1)}k` : Math.round(v).toLocaleString());
</script>

<div class="trends">
  <Sparkline
    samples={ctx.trends.samples}
    pick={(s) => (s.speed == null ? null : kmh ? s.speed * 3.6 : s.speed)}
    label="Speed"
    unit={kmh ? "km/h" : "m/s"}
    format={(v) => speed(v)}
  />
  <Sparkline samples={ctx.trends.samples} pick={(s) => s.alt} label="Altitude" unit="m" zero={false} format={fmtAlt} />
  <Sparkline samples={ctx.trends.samples} pick={(s) => s.g} label="G-force" unit="g" format={(v) => v.toFixed(1)} height={30} />
</div>

<style>
  .trends {
    display: grid;
    gap: 6px;
  }
</style>
