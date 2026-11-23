<script lang="ts">
  import type { PanelCtx } from "../../lib/context";
  import { num, temp } from "../../lib/format";
  import Ring from "../gauges/Ring.svelte";

  let { ctx }: { ctx: PanelCtx } = $props();
  const v = $derived(ctx.snap.vitals);
  const bpm = $derived(v?.heart_rate ?? null);
  const beat = $derived(bpm && bpm > 20 ? 60 / bpm : null);
  const where = $derived(
    ctx.snap.status?.locomotion === "eva" ? "EVA" : ctx.snap.status?.locomotion === "seated" ? "Seated" : "On foot",
  );
</script>

{#if !v}
  <p class="muted">No vitals yet.</p>
{:else}
  <div class="rings">
    <Ring label="Health" value={v.health} />
    <Ring label="Oxygen" value={v.oxygen} />
    <Ring label="Hunger" value={v.hunger} />
    <Ring label="Thirst" value={v.thirst} />
  </div>
  <div class="heart" class:fast={bpm != null && bpm > 150}>
    <svg viewBox="0 0 200 40" preserveAspectRatio="none" aria-hidden="true">
      <g class="trace" style:animation-duration={beat ? `${beat}s` : "0s"} class:still={!beat}>
        <path d="M0 22 H30 l6 -4 l4 4 H52 l4 -18 l5 32 l4 -14 H90 q8 -8 16 0 H200 M200 22 H230 l6 -4 l4 4 H252 l4 -18 l5 32 l4 -14 H290 q8 -8 16 0 H400" />
      </g>
    </svg>
    <div class="hr">
      <span class="big num">{num(bpm, 0)}<small>bpm</small></span>
      <span class="sub">Body {temp(v.body_temp)} · {where}</span>
    </div>
  </div>
  {#if v.intoxication}<span class="chip warn">Intoxication {v.intoxication}</span>{/if}
{/if}

<style>
  .rings {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 10px;
  }
  @container panel (max-width: 300px) {
    .rings {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }
  .heart {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
    gap: 14px;
    margin-top: 16px;
    padding: 8px 12px;
    border-radius: var(--radius-sm);
    border: 1px solid var(--line);
    background: var(--bg-2);
    --c: var(--good);
  }
  .heart.fast {
    --c: var(--warn);
  }
  svg {
    width: 100%;
    height: 40px;
    overflow: hidden;
  }
  .trace {
    animation: ecg linear infinite;
  }
  .trace.still {
    animation: none;
  }
  .trace path {
    fill: none;
    stroke: var(--c);
    stroke-width: 2;
    stroke-linejoin: round;
    vector-effect: non-scaling-stroke;
    filter: drop-shadow(0 0 3px var(--c));
  }
  @keyframes ecg {
    to {
      transform: translateX(-200px);
    }
  }
  .hr {
    display: grid;
    justify-items: end;
  }
  .big {
    font-size: 1.5rem;
    font-weight: 700;
    line-height: 1.1;
  }
  .big small {
    font-size: 0.5em;
    color: var(--text-3);
    margin-left: 4px;
  }
  .sub {
    font-size: 0.74rem;
    color: var(--text-3);
    white-space: nowrap;
  }
  .chip {
    margin-top: 10px;
  }
  .muted {
    color: var(--text-3);
    margin: 0;
  }
</style>
