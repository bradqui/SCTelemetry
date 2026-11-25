<script lang="ts">
  import type { ShipCtx } from "../../lib/context";
  import { niceMax, num, pct, speedIn } from "../../lib/format";
  import AltTape from "../gauges/AltTape.svelte";
  import ArcGauge from "../gauges/ArcGauge.svelte";
  import MiniArc from "../gauges/MiniArc.svelte";

  let { ctx }: { ctx: ShipCtx } = $props();

  const f = $derived(ctx.ship.flight);
  const quantum = $derived(f.quantum === true);
  const kmh = $derived(ctx.prefs.speedUnit === "kmh");
  const factor = $derived(kmh ? 3.6 : 1);
  const sp = $derived(speedIn(f.speed, ctx.prefs.speedUnit));
  const scale = $derived(
    niceMax(Math.max(ctx.trends.peakSpeed, f.speed ?? 0) * factor * 1.04, kmh ? 400 : 100),
  );
  const mode = $derived(ctx.ship.master_mode);

  // Vertical speed as a bar either side of zero, on a log-ish scale (±500 m/s at the ends).
  const vsiFrac = $derived(
    f.vsi == null ? 0 : Math.sign(f.vsi) * Math.min(1, Math.log10(1 + Math.abs(f.vsi)) / Math.log10(501)),
  );
  const gScale = $derived(niceMax(Math.max(f.g_max ?? 0, f.g ?? 0, 6), 6));
  const gTone = $derived(f.g == null ? "" : f.g > 9 ? "bad" : f.g > 5 ? "warn" : "");

  // Quantum route from Game.log, if the agent has one.
  const route = $derived(ctx.snap.location?.route ?? null);
  const routeState = $derived(
    !route
      ? ""
      : quantum
        ? "Jumping"
        : { plotted: "Plotted", en_route: "En route", arrived: "Arrived", blocked: "Obstructed" }[route.state],
  );
</script>

<div class="flight" class:quantum>
  <div class="dial">
    <ArcGauge
      value={quantum ? scale : f.speed == null ? null : f.speed * factor}
      max={scale}
      display={quantum ? "QT" : sp.value}
      unit={quantum ? "JUMP" : sp.unit.toUpperCase()}
      caption={quantum ? "QUANTUM" : (mode ?? (ctx.ship.powered === false ? "OFF" : ""))}
      tone={quantum ? "nav" : f.boost_engaged ? "warn" : mode === "NAV" ? "nav" : "accent"}
      peak={quantum || !ctx.trends.peakSpeed ? null : ctx.trends.peakSpeed * factor}
      inner={f.boost_reserve}
      innerLabel={f.boost_reserve == null ? "" : `BOOST ${pct(f.boost_reserve)}`}
      tickFormat={(v) => (v >= 1000 ? `${+(v / 1000).toFixed(1)}k` : String(Math.round(v)))}
    />
  </div>

  <div class="tiles">
    <div class="tape"><AltTape alt={f.alt} agl={f.radar_alt} /></div>
    <div class="vsi"><MiniArc
      label="Vert speed"
      display={quantum ? "—" : num(f.vsi, 0)}
      unit="m/s"
      centred
      frac={quantum ? null : vsiFrac}
      tone={vsiFrac < 0 ? "warn" : "good"}
    /></div>
    <div class="g"><MiniArc
      label="G-force"
      display={num(f.g, 1)}
      unit="g"
      frac={f.g == null ? null : f.g / gScale}
      peak={f.g_max ? f.g_max / gScale : null}
      danger={9 / gScale}
      tone={gTone === "bad" ? "bad" : gTone === "warn" ? "warn" : "accent"}
    /></div>
    <div class="atmo">
      <span class="label">Atmosphere</span>
      <span class="num" class:word={f.atmo_density != null && f.atmo_density < 0.005}>
        {f.atmo_density == null ? "—" : f.atmo_density < 0.005 ? "VACUUM" : num(f.atmo_density, 2)}
        {#if f.atmo_density != null && f.atmo_density >= 0.005}<small>kg/m³</small>{/if}
      </span>
    </div>
  </div>

  {#if route}
    <div class="route {route.state}" class:jumping={quantum}>
      <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M1.5 8h4 M4 5.5 6.5 8 4 10.5 M8 8h6.5 M11.5 5l3 3-3 3" /></svg>
      <span class="label">Route</span>
      <b>{route.destination ?? "Unknown"}</b>
      <em>{routeState}</em>
    </div>
  {/if}

  <div class="chips">
    {#if quantum}<span class="chip nav pulse">Quantum</span>{/if}
    <span class="chip" class:on={f.coupled} class:warn={f.coupled === false}>
      {f.coupled === false ? "Decoupled" : "Coupled"}
    </span>
    <span class="chip" class:on={f.g_safe} class:warn={f.g_safe === false}>G-safe</span>
    <span class="chip" class:on={f.cruise}>Cruise</span>
    <span class="chip" class:on={f.prox_assist}>Prox</span>
    <span class="chip" class:warn={f.boost_engaged} class:pulse={f.boost_engaged}>Boost</span>
  </div>
</div>

<style>
  .flight {
    display: grid;
    grid-template-columns: minmax(150px, 0.9fr) minmax(0, 1.2fr);
    grid-template-areas: "dial tiles" "route route" "chips chips";
    gap: 4px 12px;
    align-items: center;
  }
  .dial {
    grid-area: dial;
    max-width: 205px;
    width: 100%;
    justify-self: center;
  }
  .quantum .dial {
    animation: qt 1.6s ease-in-out infinite;
  }
  @keyframes qt {
    50% {
      filter: drop-shadow(0 0 10px var(--nav));
    }
  }
  .tiles {
    grid-area: tiles;
    display: grid;
    grid-template-columns: 62px repeat(2, minmax(0, 1fr));
    grid-template-rows: auto auto;
    grid-template-areas: "tape vsi g" "tape atmo atmo";
    gap: 6px 10px;
    align-items: start;
  }
  .tape {
    grid-area: tape;
    align-self: stretch;
  }
  .vsi {
    grid-area: vsi;
    min-width: 0;
  }
  .g {
    grid-area: g;
    min-width: 0;
  }
  .atmo {
    grid-area: atmo;
    display: flex;
    align-items: baseline;
    gap: 8px;
    padding: 4px 8px;
    border-radius: var(--radius-sm);
    border: 1px solid var(--line);
    background: color-mix(in srgb, var(--bg-2) 70%, transparent);
    min-width: 0;
  }
  .atmo .num {
    font-size: 0.95rem;
    font-weight: 700;
    white-space: nowrap;
  }
  .atmo .num.word {
    font-size: 0.78rem;
    letter-spacing: 0.12em;
    color: var(--text-2);
  }
  .atmo small {
    font-size: 0.65em;
    color: var(--text-3);
    margin-left: 3px;
  }
  .chips {
    grid-area: chips;
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }
  @container panel (max-width: 400px) {
    .flight {
      grid-template-columns: minmax(0, 1fr);
      grid-template-areas: "dial" "tiles" "route" "chips";
    }
    .dial {
      max-width: 180px;
    }
  }
  .route {
    grid-area: route;
    display: flex;
    align-items: center;
    gap: 7px;
    padding: 4px 8px;
    border: 1px solid var(--line);
    border-left: 3px solid var(--nav);
    border-radius: var(--radius-sm);
    background: color-mix(in srgb, var(--nav) 7%, var(--bg-2));
    min-width: 0;
  }
  .route svg {
    width: 13px;
    height: 13px;
    flex: none;
  }
  .route path {
    fill: none;
    stroke: var(--nav);
    stroke-width: 1.6;
    stroke-linecap: round;
    stroke-linejoin: round;
  }
  .route b {
    font-size: 0.86rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    min-width: 0;
  }
  .route em {
    margin-left: auto;
    font-style: normal;
    font-size: 0.64rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--nav);
    flex: none;
  }
  .route.jumping {
    animation: pulse 1.2s ease-in-out infinite;
  }
  .route.arrived {
    border-left-color: var(--good);
  }
  .route.arrived em {
    color: var(--good);
  }
  .route.blocked {
    border-left-color: var(--warn);
  }
  .route.blocked em {
    color: var(--warn);
  }
  .pulse {
    animation: pulse 0.9s ease-in-out infinite;
  }
</style>
