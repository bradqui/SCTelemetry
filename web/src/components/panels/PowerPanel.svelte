<script lang="ts">
  import type { ShipCtx } from "../../lib/context";

  let { ctx }: { ctx: ShipCtx } = $props();

  // The power plant feeds a bus; each system hangs off it. A system that's on is a lit
  // pill with a feed line from the bus; one that's off is a dashed outline with no feed.
  const ORDER: [string, string][] = [
    ["engines", "Engines"],
    ["shield_generators", "Shield gen"],
    ["shield_emitters", "Emitters"],
    ["weapons", "Weapons"],
    ["coolers", "Coolers"],
    ["life_support", "Life support"],
    ["sensors", "Sensors"],
    ["gravity_generators", "Gravity"],
  ];
  const plant = $derived(ctx.ship.power.powerplants);
  const systems = $derived(ORDER.filter(([k]) => ctx.ship.power[k] !== undefined));

  // The game has no quantum drive power flag. Its warning light is lit when the
  // drive is available (NAV) and off in SCM; the jump itself is inferred.
  const qdrv = $derived(ctx.ship.lights.qdrv);
  const quantum = $derived(
    ctx.ship.flight.quantum
      ? { on: true, state: "Jumping", cls: "jump" }
      : qdrv === undefined
        ? null
        : qdrv === "off"
          ? { on: false, state: "SCM", cls: "" }
          : qdrv === "nominal"
            ? { on: true, state: "Ready", cls: "" }
            : { on: true, state: "Fault", cls: "fault" },
  );
  const total = $derived(systems.length + (plant === undefined ? 0 : 1) + (quantum ? 1 : 0));
  const online = $derived(
    systems.filter(([k]) => ctx.ship.power[k]).length + (plant ? 1 : 0) + (quantum?.on ? 1 : 0),
  );
</script>

{#if total === 0}
  <p class="muted">No power data for this ship.</p>
{:else}
  <div class="summary">
    <span class="count num"><b>{online}</b>/{total}</span>
    <span class="label">online</span>
  </div>
  <div class="bus" class:live={plant !== false}>
    <div class="plant" class:on={plant}>
      <span class="name">Power plant</span><em>{plant ? "On" : plant === false ? "Off" : "?"}</em>
    </div>
    <div class="feeds">
      {#each systems as [key, name] (key)}
        {@const on = ctx.ship.power[key] === true}
        <div class="sys" class:on>
          <span class="name">{name}</span><em>{on ? "On" : "Off"}</em>
        </div>
      {/each}
      {#if quantum}
        <div class="sys {quantum.cls}" class:on={quantum.on} title="Quantum drive: {quantum.state}">
          <span class="name">Quantum</span><em>{quantum.state}</em>
        </div>
      {/if}
    </div>
  </div>
{/if}

<style>
  .summary {
    display: flex;
    align-items: baseline;
    gap: 6px;
    margin-bottom: 6px;
  }
  .count {
    font-size: 1.15rem;
    color: var(--text-3);
    font-weight: 600;
  }
  .count b {
    color: var(--text);
    font-weight: 750;
  }
  .bus {
    --feed: var(--accent);
    display: grid;
    gap: 0;
  }
  .plant,
  .sys {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 6px;
    min-width: 0;
    padding: 2px 9px;
    border-radius: 999px;
    font-size: 0.74rem;
    font-weight: 550;
    color: var(--text-3);
    border: 1px dashed var(--line-2);
  }
  .name {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  em {
    font-style: normal;
    font-size: 0.6rem;
    font-weight: 750;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    flex: none;
  }
  .on {
    color: var(--text);
    border: 1px solid var(--feed);
    background: color-mix(in srgb, var(--feed) 18%, transparent);
  }
  .on em {
    color: var(--feed);
  }
  .plant {
    justify-self: start;
    min-width: 150px;
    margin-bottom: 6px;
  }
  /* The bus: a spine down from the power plant, and a rail above each row of systems, so
     every system is fed from the plant directly (never through the one above it). Rows are
     22 px with 12 px between them: rails sit 5 px into each 34 px step. */
  .feeds {
    --rail: var(--line-2);
    position: relative;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(108px, 1fr));
    grid-auto-rows: 22px;
    gap: 12px 6px;
    padding: 12px 0 0 14px;
    background: repeating-linear-gradient(
      to bottom,
      transparent 0 5px,
      var(--rail) 5px 8px,
      transparent 8px 34px
    );
  }
  .bus.live .feeds {
    --rail: var(--feed);
  }
  .feeds::before {
    content: "";
    position: absolute;
    left: 0;
    top: -6px;
    bottom: 26px;
    width: 3px;
    background: var(--rail);
  }
  /* Each powered system's feed from its rail. */
  .sys.on::before {
    content: "";
    position: absolute;
    left: 50%;
    top: -5px;
    width: 2px;
    height: 5px;
    background: var(--feed);
  }
  .sys {
    height: 22px;
    box-sizing: border-box;
  }
  .sys.jump {
    --feed: var(--nav);
  }
  .sys.fault {
    --feed: var(--bad);
  }
  .muted {
    color: var(--text-3);
  }
</style>
