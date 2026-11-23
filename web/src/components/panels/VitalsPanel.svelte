<script lang="ts">
  import type { PanelCtx } from "../../lib/context";
  import { num, temp } from "../../lib/format";
  import Ring from "../gauges/Ring.svelte";

  let { ctx }: { ctx: PanelCtx } = $props();
  const v = $derived(ctx.snap.vitals);
  const bpm = $derived(v?.heart_rate ?? null);
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
  <div class="stats">
    <div class="stat">
      <span class="label">Heart</span>
      <span class="val num" class:warn={bpm != null && bpm > 150}>{num(bpm, 0)}<small>bpm</small></span>
    </div>
    <div class="stat">
      <span class="label">Body</span>
      <span class="val num">{temp(v.body_temp)}</span>
    </div>
    <div class="stat">
      <span class="label">State</span>
      <span class="val">{where}</span>
    </div>
    {#if v.intoxication}
      <div class="stat">
        <span class="label">Intox</span>
        <span class="val num warn">{v.intoxication}</span>
      </div>
    {/if}
  </div>
  {#if v.injuries?.length}
    <div class="injuries" aria-label="Injuries">
      {#each v.injuries as inj (inj.part)}
        <span class="inj {inj.severity}" title="{inj.severity} injury: tier {inj.tier} treatment required">
          {inj.part}<b>{inj.severity}</b><em>T{inj.tier}</em>
        </span>
      {/each}
    </div>
  {/if}
{/if}

<style>
  .injuries {
    display: flex;
    flex-wrap: wrap;
    gap: 3px;
    margin-top: 6px;
  }
  .inj {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 2px 6px;
    border-radius: 2px;
    font-size: 0.72rem;
    font-weight: 650;
    border: 1px solid var(--c);
    background: color-mix(in srgb, var(--c) 12%, transparent);
    --c: var(--warn);
  }
  .inj.moderate {
    --c: #ff8a3d;
  }
  .inj.severe {
    --c: var(--bad);
  }
  .inj b {
    font-size: 0.6rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--c);
  }
  .inj em {
    font-style: normal;
    font-family: var(--mono);
    font-size: 0.66rem;
    color: var(--text-3);
  }
  .rings {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 6px;
  }
  .stats {
    display: flex;
    gap: 4px;
    margin-top: 8px;
  }
  .stat {
    flex: 1;
    display: grid;
    gap: 1px;
    padding: 4px 7px;
    border: 1px solid var(--line);
    background: var(--bg-2);
    border-radius: 2px;
    min-width: 0;
  }
  .val {
    font-weight: 700;
    font-size: 0.9rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .val small {
    font-size: 0.65em;
    color: var(--text-3);
    margin-left: 3px;
  }
  .warn {
    color: var(--warn);
  }
  .muted {
    color: var(--text-3);
    margin: 0;
  }
</style>
