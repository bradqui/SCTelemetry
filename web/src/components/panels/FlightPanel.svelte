<script lang="ts">
  import type { ShipCtx } from "../../lib/context";
  import { altitude, niceMax, num, pct, speedIn } from "../../lib/format";
  import ArcGauge from "../gauges/ArcGauge.svelte";

  let { ctx }: { ctx: ShipCtx } = $props();

  const f = $derived(ctx.ship.flight);
  const kmh = $derived(ctx.prefs.speedUnit === "kmh");
  const factor = $derived(kmh ? 3.6 : 1);
  const sp = $derived(speedIn(f.speed, ctx.prefs.speedUnit));
  const scale = $derived(
    niceMax(Math.max(ctx.trends.peakSpeed, f.speed ?? 0) * factor * 1.04, kmh ? 400 : 100),
  );
  const alt = $derived(altitude(f.alt));
  const radar = $derived(altitude(f.radar_alt));
  const mode = $derived(ctx.ship.master_mode);

  // Vertical speed as a bar either side of zero, on a log-ish scale (±500 m/s at the ends).
  const vsiFrac = $derived(
    f.vsi == null ? 0 : Math.sign(f.vsi) * Math.min(1, Math.log10(1 + Math.abs(f.vsi)) / Math.log10(501)),
  );
  const gScale = $derived(niceMax(Math.max(f.g_max ?? 0, f.g ?? 0, 6), 6));
  const gTone = $derived(f.g == null ? "" : f.g > 9 ? "bad" : f.g > 5 ? "warn" : "");
</script>

<div class="flight">
  <div class="dial">
    <ArcGauge
      value={f.speed == null ? null : f.speed * factor}
      max={scale}
      display={sp.value}
      unit={sp.unit.toUpperCase()}
      caption={mode ?? (ctx.ship.powered === false ? "OFF" : "")}
      tone={f.boost_engaged ? "warn" : mode === "NAV" ? "nav" : "accent"}
      peak={ctx.trends.peakSpeed ? ctx.trends.peakSpeed * factor : null}
      inner={f.boost_reserve}
      innerLabel={f.boost_reserve == null ? "" : `BOOST ${pct(f.boost_reserve)}`}
      tickFormat={(v) => (v >= 1000 ? `${+(v / 1000).toFixed(1)}k` : String(Math.round(v)))}
    />
  </div>

  <div class="tiles">
    <div class="tile">
      <span class="label">Altitude</span>
      <span class="big num" class:word={f.alt == null}>{alt.value}<small>{alt.unit}</small></span>
      <span class="sub">
        {#if f.radar_alt != null}Radar <b class="num">{radar.value}{radar.unit}</b>{:else}Above ground —{/if}
      </span>
    </div>

    <div class="tile">
      <span class="label">Vertical speed</span>
      <div class="vsi-row">
        <span class="big num">{num(f.vsi, 0)}<small>m/s</small></span>
        <div class="vsi" aria-hidden="true">
          <span class="zero"></span>
          <span
            class="vbar"
            class:down={vsiFrac < 0}
            style:height="{Math.abs(vsiFrac) * 50}%"
            style:bottom={vsiFrac >= 0 ? "50%" : `${50 - Math.abs(vsiFrac) * 50}%`}
          ></span>
        </div>
      </div>
      <span class="sub">{f.vsi == null ? "" : f.vsi > 1 ? "Climbing" : f.vsi < -1 ? "Descending" : "Level"}</span>
    </div>

    <div class="tile">
      <span class="label">G-force</span>
      <span class="big num {gTone}">{num(f.g, 1)}<small>g</small></span>
      <div class="gbar" aria-hidden="true">
        <span class="gfill {gTone}" style:width="{Math.min(1, (f.g ?? 0) / gScale) * 100}%"></span>
        {#if f.g_max}<span class="gpeak" style:left="{Math.min(1, f.g_max / gScale) * 100}%"></span>{/if}
      </div>
      <span class="sub">Peak <b class="num">{num(f.g_max, 1)}g</b></span>
    </div>

    <div class="tile">
      <span class="label">Atmosphere</span>
      <span class="big num" class:word={f.atmo_density != null && f.atmo_density < 0.005}>
        {f.atmo_density == null ? "—" : f.atmo_density < 0.005 ? "VACUUM" : num(f.atmo_density, 2)}
        {#if f.atmo_density != null && f.atmo_density >= 0.005}<small>kg/m³</small>{/if}
      </span>
      <span class="sub">{f.atmo_density != null && f.atmo_density >= 0.005 ? "In atmosphere" : "Space"}</span>
    </div>
  </div>

  <div class="chips">
    <span class="chip" class:on={f.coupled} class:warn={f.coupled === false}>
      {f.coupled === false ? "Decoupled" : "Coupled"}
    </span>
    <span class="chip" class:on={f.g_safe} class:warn={f.g_safe === false}>G-safe</span>
    <span class="chip" class:on={f.cruise}>Cruise</span>
    <span class="chip" class:on={f.prox_assist}>Prox assist</span>
    <span class="chip" class:warn={f.boost_engaged} class:pulse={f.boost_engaged}>Boost</span>
  </div>
</div>

<style>
  .flight {
    display: grid;
    grid-template-columns: minmax(180px, 0.95fr) minmax(0, 1.2fr);
    grid-template-areas: "dial tiles" "chips chips";
    gap: 6px 20px;
    align-items: center;
  }
  .dial {
    grid-area: dial;
    max-width: 290px;
    width: 100%;
    justify-self: center;
  }
  .tiles {
    grid-area: tiles;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
  }
  .chips {
    grid-area: chips;
    display: flex;
    flex-wrap: wrap;
    gap: 7px;
    margin-top: 8px;
  }
  @container panel (max-width: 520px) {
    .flight {
      grid-template-columns: minmax(0, 1fr);
      grid-template-areas: "dial" "tiles" "chips";
    }
    .dial {
      max-width: 250px;
    }
  }
  .tile {
    display: grid;
    gap: 3px;
    padding: 10px 12px;
    border-radius: var(--radius-sm);
    background: color-mix(in srgb, var(--bg-2) 70%, transparent);
    border: 1px solid var(--line);
    min-width: 0;
  }
  .big {
    font-size: 1.55rem;
    font-weight: 700;
    line-height: 1.1;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .big.word {
    font-size: 1.05rem;
    letter-spacing: 0.12em;
    line-height: 1.7rem;
    color: var(--text-2);
  }
  .big small {
    font-size: 0.5em;
    color: var(--text-3);
    margin-left: 4px;
    font-weight: 600;
    letter-spacing: 0.06em;
  }
  .big.warn {
    color: var(--warn);
  }
  .big.bad {
    color: var(--bad);
  }
  .sub {
    font-size: 0.74rem;
    color: var(--text-3);
    min-height: 1em;
  }
  .sub b {
    color: var(--text-2);
    font-weight: 600;
  }
  .vsi-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }
  .vsi {
    position: relative;
    width: 8px;
    height: 34px;
    border-radius: 4px;
    background: var(--bg-2);
    border: 1px solid var(--line);
    flex: none;
  }
  .zero {
    position: absolute;
    left: -3px;
    right: -3px;
    top: 50%;
    height: 1px;
    background: var(--text-3);
  }
  .vbar {
    position: absolute;
    left: 0;
    right: 0;
    background: var(--good);
    border-radius: 3px;
    transition:
      height 0.2s linear,
      bottom 0.2s linear;
  }
  .vbar.down {
    background: var(--warn);
  }
  .gbar {
    position: relative;
    height: 6px;
    border-radius: 3px;
    background: var(--bg-2);
    border: 1px solid var(--line);
    margin: 3px 0 1px;
  }
  .gfill {
    position: absolute;
    inset: 0 auto 0 0;
    border-radius: 3px;
    background: var(--accent);
    transition: width 0.15s linear;
  }
  .gfill.warn {
    background: var(--warn);
  }
  .gfill.bad {
    background: var(--bad);
  }
  .gpeak {
    position: absolute;
    top: -3px;
    bottom: -3px;
    width: 2px;
    background: var(--text-2);
  }
  .pulse {
    animation: pulse 0.9s ease-in-out infinite;
  }
</style>
