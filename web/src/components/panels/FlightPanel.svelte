<script lang="ts">
  import type { ShipCtx } from "../../lib/context";
  import { niceMax, num, pct, speedIn } from "../../lib/format";
  import AltTape from "../gauges/AltTape.svelte";
  import ArcGauge from "../gauges/ArcGauge.svelte";
  import HeadingTape from "../gauges/HeadingTape.svelte";
  import MiniArc from "../gauges/MiniArc.svelte";
  import Sparkline from "../gauges/Sparkline.svelte";
  import { showing } from "../../lib/panels";
  import { speed as fmtSpeed } from "../../lib/format";

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

  // The compass and the history live here when their own panels aren't on screen (the
  // built-in layouts since 0.10): the compass along the top, each history under its gauge.
  const compass = $derived(!showing(ctx.prefs, ctx.compact, "heading"));
  // Not in Compact: a narrow VR column has no room for three strips (add Trends there).
  const history = $derived(!ctx.compact && !showing(ctx.prefs, ctx.compact, "trends"));
  const fmtAlt = (v: number) => (Math.abs(v) >= 10_000 ? `${(v / 1000).toFixed(1)}k` : Math.round(v).toLocaleString());

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

{#if compass}
  <div class="compass">
    <HeadingTape
      heading={f.heading}
      compact
      note={f.heading == null && f.alt == null ? "No heading in deep space" : "No heading"}
    />
  </div>
{/if}
<div class="flight" class:quantum class:history>
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
  <div class="tape"><AltTape alt={f.alt} agl={f.radar_alt} /></div>
  <div class="vsi"><MiniArc
    label="Vert speed"
    display={quantum ? "—" : num(f.vsi, 0)}
    unit="m/s"
    centred
    large
    frac={quantum ? null : vsiFrac}
    tone={vsiFrac < 0 ? "warn" : "good"}
  /></div>
  <div class="g"><MiniArc
    label="G-force"
    display={num(f.g, 1)}
    unit="g"
    large
    frac={f.g == null ? null : f.g / gScale}
    peak={f.g_max ? f.g_max / gScale : null}
    danger={9 / gScale}
    tone={gTone === "bad" ? "bad" : gTone === "warn" ? "warn" : "accent"}
  /></div>
  {#if history}
    <div class="tr sp">
      <Sparkline
        samples={ctx.trends.samples}
        pick={(s) => (s.speed == null ? null : s.speed * factor)}
        label="Speed"
        unit={kmh ? "km/h" : "m/s"}
        format={(v) => fmtSpeed(v)}
        height={44}
      />
    </div>
    <div class="tr al">
      <Sparkline samples={ctx.trends.samples} pick={(s) => s.alt} label="Altitude" unit="m" zero={false} format={fmtAlt} height={44} />
    </div>
    <div class="tr gt">
      <Sparkline samples={ctx.trends.samples} pick={(s) => s.g} label="G" unit="g" format={(v) => v.toFixed(1)} height={44} />
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
  {#if route}
      <div class="route {route.state}" class:jumping={quantum}>
        <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M1.5 8h4 M4 5.5 6.5 8 4 10.5 M8 8h6.5 M11.5 5l3 3-3 3" /></svg>
        <span class="label">Route</span>
        <b>{route.destination ?? "Unknown"}</b>
        <em>{routeState}</em>
      </div>
    {/if}
    <span class="atmo">
      <span class="label">Atmosphere</span>
      <b class="num" class:word={f.atmo_density != null && f.atmo_density < 0.005}
        >{f.atmo_density == null ? "—" : f.atmo_density < 0.005 ? "Vacuum" : num(f.atmo_density, 2)}</b
      >{#if f.atmo_density != null && f.atmo_density >= 0.005}<small>kg/m³</small>{/if}
    </span>
  </div>
</div>

<style>
  .compass {
    margin: -2px 0 6px;
  }
  /* Speed dial, altitude tape, climb and G in a row; their history under them. */
  .flight {
    display: grid;
    grid-template-columns: minmax(160px, 1fr) 66px minmax(0, 0.8fr) minmax(0, 0.8fr);
    grid-template-areas:
      "dial tape vsi g"
      "chips chips chips chips";
    gap: 6px 12px;
    align-items: stretch;
  }
  .flight.history {
    grid-template-areas:
      "dial tape vsi g"
      "sp al al gt"
      "chips chips chips chips";
  }
  .dial {
    grid-area: dial;
    max-width: 232px;
    width: 100%;
    justify-self: center;
    align-self: center;
  }
  .quantum .dial {
    animation: qt 1.6s ease-in-out infinite;
  }
  @keyframes qt {
    50% {
      filter: drop-shadow(0 0 10px var(--nav));
    }
  }
  .tape {
    grid-area: tape;
  }
  .vsi {
    grid-area: vsi;
    min-width: 0;
  }
  .g {
    grid-area: g;
    min-width: 0;
  }
  .tr {
    min-width: 0;
    overflow: hidden;
    padding-top: 4px;
    border-top: 1px solid var(--line);
  }
  .sp {
    grid-area: sp;
  }
  .al {
    grid-area: al;
  }
  .gt {
    grid-area: gt;
  }
  @container panel (max-width: 560px) {
    .flight,
    .flight.history {
      grid-template-columns: 62px minmax(0, 1fr) minmax(0, 1fr);
      grid-template-areas:
        "dial dial dial"
        "tape vsi g"
        "sp sp sp"
        "al al al"
        "gt gt gt"
        "chips chips chips";
    }
    .dial {
      max-width: 200px;
    }
  }
  .chips .route {
    flex: 1 1 240px;
    min-width: 0;
    margin: 0;
  }
  .atmo {
    margin-left: auto;
    display: inline-flex;
    align-items: baseline;
    gap: 6px;
    font-size: 0.8rem;
  }
  .atmo b {
    font-weight: 700;
  }
  .atmo b.word {
    color: var(--text-2);
  }
  .atmo small {
    font-size: 0.7em;
    color: var(--text-3);
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
