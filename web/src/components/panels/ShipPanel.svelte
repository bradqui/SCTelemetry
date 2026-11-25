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

  // The shield ring: four faces (front, right, back, left) around an arrow for your ship,
  // nose up. The game only says whether shields are powered, so the four light together;
  // if it ever sends each face's level, each arc shows its own (as many as it sends).
  const CX = 80;
  const CY = 82;
  const RX = 58;
  const RY = 66;
  function faceArc(i: number, n: number): string {
    const step = 360 / n;
    const gap = n <= 4 ? 10 : 8;
    const a0 = ((-90 + step * i - step / 2 + gap / 2) * Math.PI) / 180;
    const a1 = ((-90 + step * i + step / 2 - gap / 2) * Math.PI) / 180;
    const p = (a: number) => `${(CX + RX * Math.cos(a)).toFixed(1)} ${(CY + RY * Math.sin(a)).toFixed(1)}`;
    return `M${p(a0)} A${RX} ${RY} 0 0 1 ${p(a1)}`;
  }
  const faces = $derived<{ tone: string; level: number | null }[]>(
    shields.faces?.length
      ? shields.faces.map((v) => ({ tone: v < 0.25 ? "bad" : v < 0.5 ? "warn" : "good", level: v }))
      : Array.from({ length: 4 }, () => ({ tone: shieldState, level: null })),
  );
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

    {#each faces as f, i (i)}
      <path class="face {f.tone}" d={faceArc(i, faces.length)} style:opacity={f.level == null ? null : 0.35 + f.level * 0.65} />
    {/each}

    {#if engines}
      <circle class="engine" class:boost cx="80" cy="108" r={boost ? 8 : 5} fill="url(#eng)" />
    {/if}
    <g class="hull {hullTone}">
      <path d="M80 46 L104 112 L80 98 L56 112 Z" />
      {#if gearDown}
        <g class="gear" class:moving={gearMoving}>
          <circle cx="80" cy="66" r="2.4" />
          <circle cx="70" cy="98" r="2.4" />
          <circle cx="90" cy="98" r="2.4" />
        </g>
      {/if}
    </g>
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

  .face {
    fill: none;
    stroke-width: 5;
    stroke-linecap: round;
    transition: stroke 0.3s;
  }
  .face.up,
  .face.good {
    stroke: var(--accent);
    filter: drop-shadow(0 0 var(--glow, 4px) color-mix(in srgb, var(--accent) 70%, transparent));
  }
  .face.warn {
    stroke: var(--warn);
  }
  .face.bad {
    stroke: var(--bad);
  }
  .face.down {
    stroke: var(--text-3);
    stroke-width: 3;
    stroke-dasharray: 2 5;
    opacity: 0.45;
  }
  .face.unknown {
    stroke: var(--line-2);
    stroke-width: 3;
    stroke-dasharray: 2 5;
  }

  .hull path {
    stroke-width: 1.8;
    stroke-linejoin: round;
    transition: fill 0.3s, stroke 0.3s;
  }
  .hull.unknown path {
    fill: color-mix(in srgb, var(--accent) 16%, var(--panel));
    stroke: var(--accent);
  }
  .hull.good path {
    fill: color-mix(in srgb, var(--good) 22%, var(--panel));
    stroke: var(--good);
  }
  .hull.warn path {
    fill: color-mix(in srgb, var(--warn) 25%, var(--panel));
    stroke: var(--warn);
  }
  .hull.bad path {
    fill: color-mix(in srgb, var(--bad) 28%, var(--panel));
    stroke: var(--bad);
    animation: pulse 1s ease-in-out infinite;
  }
  .gear circle {
    fill: var(--text-2);
  }
  .gear.moving circle {
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
