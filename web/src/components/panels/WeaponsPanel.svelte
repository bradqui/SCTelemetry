<script lang="ts">
  import type { PanelCtx } from "../../lib/context";
  import { titleCase } from "../../lib/format";

  let { ctx }: { ctx: PanelCtx } = $props();
  const w = $derived(ctx.snap.weapons);
  const ready = $derived(w ? w.guns.filter((g) => g.ready).length : 0);
  const total = $derived(w?.guns.length ?? 0);

  // Guns as pips around a small reticle (up to 12; more and the list says the rest).
  const pips = $derived(
    (w?.guns ?? []).slice(0, 12).map((g, i, all) => {
      const n = all.length;
      const a = n === 1 ? 0 : -150 + (300 / (n - 1)) * i; // degrees from straight up
      const r = (a * Math.PI) / 180;
      return { x: 30 + 22 * Math.sin(r), y: 30 - 22 * Math.cos(r), ready: g.ready, powered: g.powered };
    }),
  );

  // Countermeasures as dials. The game sends how many are left, not a capacity, so each dial
  // is measured against the most seen on this ship this session.
  const most = new Map<string, number>();
  const cms = $derived(
    (w?.countermeasures ?? []).map((cm) => {
      const key = `${ctx.snap.ship?.id ?? "?"}:${cm.type}`;
      const top = Math.max(most.get(key) ?? 0, cm.count);
      most.set(key, top);
      return { type: cm.type, count: cm.count, frac: top ? cm.count / top : 0 };
    }),
  );
  function dial(frac: number): string {
    const R = 17;
    const a0 = (-140 * Math.PI) / 180;
    const a1 = ((-140 + 280 * Math.max(0, Math.min(1, frac))) * Math.PI) / 180;
    const p = (a: number) => `${(22 + R * Math.sin(a)).toFixed(1)} ${(22 - R * Math.cos(a)).toFixed(1)}`;
    return `M${p(a0)} A${R} ${R} 0 ${a1 - a0 > Math.PI ? 1 : 0} 1 ${p(a1)}`;
  }
</script>

{#if !w}
  <p class="muted">No weapons data for this seat.</p>
{:else}
  <div class="top">
    <div class="reticle" role="img" aria-label="{ready} of {total} guns ready">
      <svg viewBox="0 0 60 60" aria-hidden="true">
        <circle cx="30" cy="30" r="11" class="ring" />
        <line x1="24" y1="30" x2="36" y2="30" class="cross" /><line x1="30" y1="24" x2="30" y2="36" class="cross" />
        {#each pips as pip, i (i)}
          <circle cx={pip.x} cy={pip.y} r="4.5" class="pip" class:ready={pip.ready} class:off={!pip.powered} />
        {/each}
      </svg>
      <span class="big num" class:warn={total > 0 && ready < total}>{ready}<small>/{total}</small></span>
    </div>
    <span class="chip" class:on={w.gimbals_locked} class:off={!w.gimbals_locked}>
      Gimbals {w.gimbals_locked ? "locked" : w.gimbals_locked === false ? "free" : "?"}
    </span>
    {#if cms.length}
      <div class="cms">
        {#each cms as cm (cm.type)}
          <div class="cm" class:empty={cm.count === 0} role="img" aria-label="{cm.count} {cm.type}s left">
            <svg viewBox="0 0 44 40" aria-hidden="true">
              <path d={dial(1)} class="dtrack" />
              {#if cm.frac > 0}<path d={dial(cm.frac)} class="dval" />{/if}
              <text x="22" y="27" text-anchor="middle" class="num dn">{cm.count}</text>
            </svg>
            <span class="label">{titleCase(cm.type)}s</span>
          </div>
        {/each}
      </div>
    {/if}
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
{/if}

<style>
  .top {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    align-items: center;
    gap: 10px;
  }
  .reticle {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .reticle svg {
    width: 56px;
    height: 56px;
    flex: none;
  }
  .ring {
    fill: none;
    stroke: var(--line-2);
  }
  .cross {
    stroke: var(--text-3);
    stroke-width: 1;
  }
  .pip {
    fill: var(--bg-2);
    stroke: var(--warn);
    stroke-width: 1.5;
  }
  .pip.ready {
    fill: var(--good);
    stroke: var(--good);
  }
  .pip.off {
    stroke: var(--line-2);
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
    gap: 6px;
  }
  .cm {
    display: grid;
    justify-items: center;
    gap: 0;
  }
  .cm svg {
    width: 46px;
    height: 42px;
  }
  .dtrack {
    fill: none;
    stroke: var(--line);
    stroke-width: 4;
    stroke-linecap: round;
  }
  .dval {
    fill: none;
    stroke: var(--accent-2, var(--accent));
    stroke-width: 4;
    stroke-linecap: round;
  }
  .dn {
    font-size: 12px;
    font-weight: 700;
    fill: var(--text);
  }
  .cm.empty .dn {
    fill: var(--bad);
  }
  .cm .label {
    font-size: 0.58rem;
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
