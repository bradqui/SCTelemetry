<script lang="ts">
  import type { ShipCtx } from "../../lib/context";
  import Bar from "../Bar.svelte";

  let { ctx }: { ctx: ShipCtx } = $props();

  const ship = $derived(ctx.ship);
  const shields = $derived(ship.shields);
  const hullTone = $derived(
    ship.hull == null ? "unknown" : ship.hull < 0.25 ? "bad" : ship.hull < 0.5 ? "warn" : "good",
  );
  const shieldState = $derived(
    shields.faces?.length ? "faces" : shields.powered === true ? "up" : shields.powered === false ? "down" : "unknown",
  );
  const shieldsNote = $derived(
    shields.powered === true ? "Up · level n/a" : shields.powered === false ? "Down" : "No data",
  );
  const engines = $derived(ship.power.engines === true);
  const boost = $derived(ship.flight.boost_engaged === true);
  const gearDown = $derived(ship.gear === "deployed" || ship.gear === "deploying");
  const gearMoving = $derived(ship.gear === "deploying" || ship.gear === "retracting");

  // Shield faces (when the game sends them) as arcs around the ship, front first.
  const CX = 80;
  const CY = 82;
  const RX = 64;
  const RY = 72;
  function faceArc(i: number, n: number): string {
    const gap = 6;
    const a0 = ((-90 + (360 / n) * i - 180 / n + gap / 2) * Math.PI) / 180;
    const a1 = ((-90 + (360 / n) * (i + 1) - 180 / n - gap / 2) * Math.PI) / 180;
    const p = (a: number) => `${(CX + RX * Math.cos(a)).toFixed(1)} ${(CY + RY * Math.sin(a)).toFixed(1)}`;
    return `M${p(a0)} A${RX} ${RY} 0 0 1 ${p(a1)}`;
  }
  const faceTone = (v: number) => (v < 0.25 ? "bad" : v < 0.5 ? "warn" : "good");
</script>

<div class="shipview">
  <svg class="diagram" viewBox="0 0 160 164" role="img" aria-label="Ship diagram: hull {ship.hull ?? 'unknown'}, shields {shieldState}">
    <defs>
      <radialGradient id="eng" cx="0.5" cy="0.5" r="0.5">
        <stop offset="0" stop-color="#fff" />
        <stop offset="0.35" stop-color="var(--accent)" />
        <stop offset="1" stop-color="transparent" />
      </radialGradient>
    </defs>

    {#if shieldState === "faces" && shields.faces}
      {#each shields.faces as v, i (i)}
        <path class="face {faceTone(v)}" d={faceArc(i, shields.faces.length)} style:opacity={0.35 + v * 0.65} />
      {/each}
    {:else}
      <ellipse class="shield {shieldState}" cx={CX} cy={CY} rx={RX} ry={RY} />
      {#if shieldState === "up"}
        <ellipse class="shimmer" cx={CX} cy={CY} rx={RX} ry={RY} pathLength="100" />
      {/if}
    {/if}

    <g class="hull {hullTone}" transform="translate(30 22)">
      <path
        d="M50 2 L57 26 L60 48 L92 68 L96 84 L62 80 L58 98 L72 108 L70 116 L50 111 L30 116 L28 108 L42 98 L38 80 L4 84 L8 68 L40 48 L43 26 Z"
      />
      <path class="detail" d="M50 30 L50 96 M40 52 L40 80 M60 52 L60 80" />
      <ellipse class="canopy" cx="50" cy="34" rx="4.5" ry="9" />
      {#if gearDown}
        <g class="gear" class:moving={gearMoving}>
          <rect x="47.5" y="18" width="5" height="7" rx="1.5" />
          <rect x="22" y="72" width="5" height="7" rx="1.5" />
          <rect x="73" y="72" width="5" height="7" rx="1.5" />
        </g>
      {/if}
    </g>
    {#if engines}
      <circle class="engine" class:boost cx="72" cy="140" r={boost ? 9 : 6} fill="url(#eng)" />
      <circle class="engine" class:boost cx="88" cy="140" r={boost ? 9 : 6} fill="url(#eng)" />
    {/if}
  </svg>

  <div class="side">
    <Bar label="Hull" value={ship.hull} empty="No data from game" />
    <Bar
      label="Shields"
      value={shields.level}
      empty={shieldsNote}
      tone={shields.level == null ? (shields.powered ? "accent" : "muted") : "auto"}
    />
    <div class="chips">
      <span class="chip" class:on={ship.powered} class:off={ship.powered !== true}>
        <span class="dot"></span>{ship.powered ? "Powered" : ship.powered === false ? "Powered down" : "Power ?"}
      </span>
      <span class="chip" class:on={engines}>Engines {engines ? "on" : "off"}</span>
      {#if ship.gear}
        <span class="chip" class:warn={gearMoving} class:pulse={gearMoving}>Gear {ship.gear}</span>
      {/if}
    </div>
  </div>
</div>

<style>
  .shipview {
    display: grid;
    grid-template-columns: minmax(100px, 0.8fr) minmax(0, 1.2fr);
    gap: 12px;
    align-items: center;
  }
  @container panel (max-width: 270px) {
    .shipview {
      grid-template-columns: minmax(0, 1fr);
    }
    .diagram {
      max-width: 130px;
    }
  }
  .diagram {
    width: 100%;
    max-width: 150px;
    max-height: 160px;
    justify-self: center;
    overflow: visible;
  }
  .side {
    display: grid;
    gap: 9px;
    min-width: 0;
  }
  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }

  .shield {
    fill: none;
    stroke-width: 3;
  }
  .shield.up {
    stroke: var(--accent);
    fill: color-mix(in srgb, var(--accent) 7%, transparent);
    filter: drop-shadow(0 0 var(--glow, 6px) var(--accent));
  }
  .shield.down {
    stroke: var(--text-3);
    stroke-dasharray: 3 6;
    opacity: 0.6;
  }
  .shield.unknown {
    stroke: var(--line-2);
    stroke-dasharray: 2 5;
  }
  .shimmer {
    fill: none;
    stroke: #ffffff;
    stroke-width: 3;
    stroke-dasharray: 6 94;
    stroke-linecap: round;
    opacity: 0.55;
    animation: orbit 4s linear infinite;
  }
  @keyframes orbit {
    to {
      stroke-dashoffset: -100;
    }
  }
  .face {
    fill: none;
    stroke-width: 5;
    stroke-linecap: round;
  }
  .face.good {
    stroke: var(--accent);
  }
  .face.warn {
    stroke: var(--warn);
  }
  .face.bad {
    stroke: var(--bad);
  }

  .hull path:first-child {
    stroke-width: 1.6;
    stroke-linejoin: round;
    transition: fill 0.3s;
  }
  .hull.unknown path:first-child {
    fill: var(--panel-2);
    stroke: var(--text-2);
  }
  .hull.good path:first-child {
    fill: color-mix(in srgb, var(--good) 22%, var(--panel));
    stroke: var(--good);
  }
  .hull.warn path:first-child {
    fill: color-mix(in srgb, var(--warn) 25%, var(--panel));
    stroke: var(--warn);
  }
  .hull.bad path:first-child {
    fill: color-mix(in srgb, var(--bad) 28%, var(--panel));
    stroke: var(--bad);
    animation: pulse 1s ease-in-out infinite;
  }
  .detail {
    fill: none;
    stroke: var(--line-2);
    stroke-width: 1;
  }
  .canopy {
    fill: color-mix(in srgb, var(--accent) 35%, var(--bg));
    stroke: var(--accent);
    stroke-width: 1;
  }
  .gear rect {
    fill: var(--text-2);
  }
  .gear.moving rect {
    fill: var(--warn);
    animation: pulse 0.7s ease-in-out infinite;
  }
  .engine {
    animation: flicker 0.18s steps(2) infinite;
  }
  .engine.boost {
    filter: drop-shadow(0 0 6px var(--accent));
  }
  @keyframes flicker {
    50% {
      opacity: 0.8;
    }
  }
  .pulse {
    animation: pulse 0.9s ease-in-out infinite;
  }
</style>
