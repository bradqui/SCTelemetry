<script lang="ts">
  import type { PanelCtx } from "../../lib/context";
  import { titleCase } from "../../lib/format";

  let { ctx }: { ctx: PanelCtx } = $props();
  const w = $derived(ctx.snap.weapons);
  const ready = $derived(w ? w.guns.filter((g) => g.ready).length : 0);
  const total = $derived(w?.guns.length ?? 0);
</script>

{#if !w}
  <p class="muted">No weapons data for this seat.</p>
{:else}
  <div class="top">
    <div class="ready">
      <span class="big num" class:warn={total > 0 && ready < total}>{ready}<small>/{total}</small></span>
      <span class="label">Guns ready</span>
    </div>
    <span class="chip" class:on={w.gimbals_locked} class:off={!w.gimbals_locked}>
      Gimbals {w.gimbals_locked ? "locked" : w.gimbals_locked === false ? "free" : "?"}
    </span>
  </div>
  {#if total}
    <ul class="guns">
      {#each w.guns as gun, i (i)}
        <li class:ready={gun.ready} class:off={!gun.powered}>
          <span class="led"></span>
          <span class="gname">{gun.name.replace(/_/g, " ")}</span>
          <span class="gstate">{!gun.powered ? "off" : gun.ready ? "ready" : "not ready"}</span>
        </li>
      {/each}
    </ul>
  {/if}
  <p class="note">The game doesn't report ammo or firing.</p>
  {#if w.countermeasures.length}
    <div class="cms">
      {#each w.countermeasures as cm (cm.type)}
        <div class="cm" class:empty={cm.count === 0}>
          <span class="n num">{cm.count}</span>
          <span class="label">{titleCase(cm.type)}s</span>
        </div>
      {/each}
    </div>
  {/if}
{/if}

<style>
  .top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 10px;
  }
  .ready {
    display: grid;
  }
  .big {
    font-size: 1.4rem;
    font-weight: 750;
    line-height: 1;
  }
  .big small {
    font-size: 0.55em;
    color: var(--text-3);
  }
  .big.warn {
    color: var(--warn);
  }
  .guns {
    list-style: none;
    padding: 0;
    margin: 6px 0 0;
    display: grid;
    gap: 2px;
  }
  .guns li {
    display: flex;
    align-items: center;
    gap: 7px;
    padding: 2px 7px;
    border-radius: var(--radius-sm);
    background: var(--bg-2);
    font-size: 0.78rem;
    color: var(--text-2);
  }
  .led {
    width: 6px;
    height: 6px;
    background: var(--warn);
    flex: none;
  }
  .ready .led {
    background: var(--good);
    box-shadow: 0 0 7px var(--good);
  }
  .off {
    color: var(--text-3);
  }
  .off .led {
    background: var(--line-2);
    box-shadow: none;
  }
  .gname {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-family: var(--mono);
    font-size: 0.76rem;
  }
  .gstate {
    font-size: 0.68rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text-3);
  }
  .cms {
    display: flex;
    gap: 4px;
    margin-top: 4px;
  }
  .cm {
    flex: 1;
    display: grid;
    justify-items: center;
    padding: 3px 6px;
    border-radius: var(--radius-sm);
    border: 1px solid var(--line);
    background: var(--bg-2);
  }
  .cm .n {
    font-size: 1.05rem;
    font-weight: 700;
  }
  .cm.empty {
    border-color: color-mix(in srgb, var(--bad) 40%, transparent);
  }
  .cm.empty .n {
    color: var(--bad);
  }
  .note {
    margin: 4px 0 0;
    font-size: 0.64rem;
    color: var(--text-3);
  }
  .muted {
    color: var(--text-3);
    margin: 0;
  }
</style>
