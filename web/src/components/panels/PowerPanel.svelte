<script lang="ts">
  import type { ShipCtx } from "../../lib/context";

  let { ctx }: { ctx: ShipCtx } = $props();

  const ORDER: [string, string][] = [
    ["powerplants", "Power plant"],
    ["engines", "Engines"],
    ["shield_generators", "Shield gen"],
    ["shield_emitters", "Emitters"],
    ["weapons", "Weapons"],
    ["coolers", "Coolers"],
    ["life_support", "Life support"],
    ["sensors", "Sensors"],
    ["gravity_generators", "Gravity"],
  ];
  const systems = $derived(ORDER.filter(([k]) => ctx.ship.power[k] !== undefined));
  const online = $derived(systems.filter(([k]) => ctx.ship.power[k]).length);
</script>

{#if systems.length === 0}
  <p class="muted">No power data for this ship.</p>
{:else}
  <div class="summary">
    <span class="count num"><b>{online}</b>/{systems.length}</span>
    <span class="label">online</span>
    <div class="seg" aria-hidden="true">
      {#each systems as [k] (k)}<span class:on={ctx.ship.power[k]}></span>{/each}
    </div>
  </div>
  <div class="grid">
    {#each systems as [key, name] (key)}
      {@const on = ctx.ship.power[key]}
      <div class="pw" class:on>
        <span class="led"></span>{name}
      </div>
    {/each}
  </div>
{/if}

<style>
  .summary {
    display: flex;
    align-items: baseline;
    gap: 8px;
    margin-bottom: 12px;
  }
  .count {
    font-size: 1.5rem;
    color: var(--text-3);
    font-weight: 600;
  }
  .count b {
    color: var(--text);
    font-weight: 750;
  }
  .seg {
    margin-left: auto;
    display: flex;
    gap: 3px;
    align-self: center;
  }
  .seg span {
    width: 10px;
    height: 14px;
    border-radius: 2px;
    background: var(--line);
  }
  .seg span.on {
    background: var(--good);
    box-shadow: 0 0 6px color-mix(in srgb, var(--good) 60%, transparent);
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(118px, 1fr));
    gap: 6px;
  }
  .pw {
    display: flex;
    align-items: center;
    gap: 9px;
    padding: 7px 10px;
    border-radius: var(--radius-sm);
    border: 1px solid var(--line);
    background: var(--bg-2);
    color: var(--text-3);
    font-size: 0.84rem;
    font-weight: 550;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .pw.on {
    color: var(--text);
    border-color: color-mix(in srgb, var(--good) 25%, transparent);
  }
  .led {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--line-2);
    flex: none;
  }
  .pw.on .led {
    background: var(--good);
    box-shadow: 0 0 8px var(--good);
  }
  .muted {
    color: var(--text-3);
    margin: 0;
  }
</style>
