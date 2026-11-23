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

  // The game has no quantum drive power flag. Its warning light is lit when the
  // drive is available (NAV) and off in SCM; the jump itself is inferred.
  const qdrv = $derived(ctx.ship.lights.qdrv);
  const quantum = $derived(
    ctx.ship.flight.quantum
      ? { on: true, state: "Jumping", cls: "jump" }
      : qdrv === undefined
        ? null
        : qdrv === "off"
          ? { on: false, state: "Off (SCM)", cls: "" }
          : qdrv === "nominal"
            ? { on: true, state: "Ready", cls: "" }
            : { on: true, state: "Fault", cls: "fault" },
  );
  const total = $derived(systems.length + (quantum ? 1 : 0));
  const online = $derived(systems.filter(([k]) => ctx.ship.power[k]).length + (quantum?.on ? 1 : 0));
</script>

{#if total === 0}
  <p class="muted">No power data for this ship.</p>
{:else}
  <div class="summary">
    <span class="count num"><b>{online}</b>/{total}</span>
    <span class="label">online</span>
    <div class="seg" aria-hidden="true">
      {#each systems as [k] (k)}<span class:on={ctx.ship.power[k]}></span>{/each}
      {#if quantum}<span class:on={quantum.on} class:jump={quantum.cls === "jump"}></span>{/if}
    </div>
  </div>
  <div class="grid">
    {#each systems as [key, name] (key)}
      <div class="pw" class:on={ctx.ship.power[key]}><span class="led"></span>{name}</div>
    {/each}
    {#if quantum}
      <div class="pw qd {quantum.cls}" class:on={quantum.on} title="Quantum drive: {quantum.state}">
        <span class="led"></span>Quantum<em>{quantum.state}</em>
      </div>
    {/if}
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
  .seg {
    margin-left: auto;
    display: flex;
    gap: 2px;
    align-self: center;
  }
  .seg span {
    width: 7px;
    height: 11px;
    background: var(--line);
  }
  .seg span.on {
    background: var(--good);
    box-shadow: 0 0 5px color-mix(in srgb, var(--good) 60%, transparent);
  }
  .seg span.jump {
    background: var(--nav);
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(98px, 1fr));
    gap: 3px;
  }
  .pw {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 3px 6px;
    border-radius: 2px;
    border: 1px solid var(--line);
    background: var(--bg-2);
    color: var(--text-3);
    font-size: 0.74rem;
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
    width: 6px;
    height: 6px;
    background: var(--line-2);
    flex: none;
  }
  .pw.on .led {
    background: var(--good);
    box-shadow: 0 0 6px var(--good);
  }
  .qd {
    grid-column: span 2;
  }
  .qd em {
    margin-left: auto;
    font-style: normal;
    font-size: 0.62rem;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-3);
  }
  .qd.jump {
    border-color: var(--nav);
    color: var(--nav);
    animation: pulse 1.2s ease-in-out infinite;
  }
  .qd.jump .led {
    background: var(--nav);
    box-shadow: 0 0 8px var(--nav);
  }
  .qd.jump em {
    color: var(--nav);
  }
  .qd.fault .led {
    background: var(--warn);
  }
  .muted {
    color: var(--text-3);
    margin: 0;
  }
</style>
