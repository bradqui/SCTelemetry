<script lang="ts">
  import type { PanelCtx } from "../../lib/context";
  import { num, temp } from "../../lib/format";
  import Readout from "../Readout.svelte";

  let { ctx }: { ctx: PanelCtx } = $props();
  const v = $derived(ctx.snap.vitals);
  const env = $derived(v?.environment ?? null);
  const vacuum = $derived(v?.pressure != null && v.pressure < 0.01);
</script>

{#if !v || !env}
  <p class="muted">No environment data yet.</p>
{:else}
  <div class="readouts">
    <Readout
      label="Outside"
      value={temp(env.temperature)}
      tone={env.temperature != null && (env.temperature < -40 || env.temperature > 60) ? "warn" : ""}
    />
    <Readout label="Gravity" value={num(v.gravity, 2)} unit="g" />
    <Readout
      label="Pressure"
      value={vacuum ? "Vacuum" : num(v.pressure, 2)}
      unit={vacuum ? "" : "atm"}
      tone={vacuum ? "warn" : ""}
    />
    <Readout label="Radiation" value={num(env.radiation, 2)} tone={env.radiation ? "warn" : ""} />
    <div class="air">
      <span class="chip" class:on={env.breathable} class:bad={env.breathable === false}>
        <span class="dot"></span>
        {env.breathable ? "Breathable air" : env.breathable === false ? "Not breathable" : "Air unknown"}
      </span>
    </div>
  </div>
{/if}

<style>
  .readouts {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(86px, 1fr));
    gap: 6px 10px;
    align-items: end;
  }
  .air {
    display: flex;
    align-items: end;
  }
  .muted {
    color: var(--text-3);
    margin: 0;
  }
</style>
