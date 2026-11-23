<script lang="ts">
  import type { Status, Vitals } from "../lib/types";
  import { num, temp } from "../lib/format";
  import Bar from "./Bar.svelte";
  import Readout from "./Readout.svelte";

  let { vitals, status, compact = false }: { vitals: Vitals; status: Status | null; compact?: boolean } =
    $props();

  const env = $derived(vitals.environment);
  const vacuum = $derived(vitals.pressure != null && vitals.pressure < 0.01);
  const where = $derived(
    status?.locomotion === "eva" ? "EVA" : status?.locomotion === "seated" ? "Seated" : "On foot",
  );
</script>

<section class="personal" class:compact>
  <div class="panel body">
    <span class="label">{compact ? "Vitals" : `Vitals · ${where}`}</span>
    <div class="bars">
      <Bar label="Health" value={vitals.health} />
      <Bar label="Oxygen" value={vitals.oxygen} />
      <Bar label="Hunger" value={vitals.hunger} />
      <Bar label="Thirst" value={vitals.thirst} />
    </div>
    <div class="readouts">
      <Readout
        label="Heart rate"
        value={num(vitals.heart_rate, 0)}
        unit="bpm"
        tone={vitals.heart_rate != null && vitals.heart_rate > 150 ? "warn" : ""}
      />
      <Readout label="Body temp" value={temp(vitals.body_temp)} />
      {#if vitals.intoxication}<Readout label="Intoxication" value={String(vitals.intoxication)} tone="warn" />{/if}
    </div>
  </div>

  {#if !compact}
    <div class="panel env">
      <span class="label">Environment</span>
      <div class="readouts">
        <Readout label="Outside" value={temp(env.temperature)} tone={env.temperature != null && (env.temperature < -40 || env.temperature > 60) ? "warn" : ""} />
        <Readout label="Gravity" value={num(vitals.gravity, 2)} unit="g" />
        <Readout label="Pressure" value={vacuum ? "Vacuum" : num(vitals.pressure, 2)} unit={vacuum ? "" : "atm"} tone={vacuum ? "warn" : ""} />
        <Readout label="Radiation" value={num(env.radiation, 2)} tone={env.radiation ? "warn" : ""} />
      </div>
      <div class="chips">
        <span class="chip" class:on={env.breathable} class:bad={env.breathable === false}>
          <span class="dot"></span>{env.breathable ? "Breathable air" : env.breathable === false ? "Not breathable" : "Air unknown"}
        </span>
      </div>
    </div>
  {/if}
</section>

<style>
  .personal {
    display: grid;
    gap: var(--gap);
    grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr);
  }
  .personal.compact {
    grid-template-columns: 1fr;
  }
  @media (max-width: 860px) {
    .personal {
      grid-template-columns: 1fr;
    }
  }
  .bars {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 14px 22px;
  }
  .readouts {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
    gap: 14px;
    margin-top: 18px;
  }
  .env .readouts {
    margin-top: 0;
  }
  .chips {
    display: flex;
    gap: 7px;
    margin-top: 16px;
  }
</style>
