<script lang="ts">
  // A 240° dial: value arc, ticks, an optional peak notch and an optional inner arc.
  let {
    value,
    max,
    display,
    unit = "",
    caption = "",
    ticks = 5,
    peak = null,
    inner = null,
    innerLabel = "",
    tone = "accent",
    tickFormat = (v: number) => String(Math.round(v)),
  }: {
    value: number | null;
    max: number;
    display: string;
    unit?: string;
    caption?: string;
    ticks?: number;
    peak?: number | null;
    /** 0-1, drawn as a thin arc inside the main one (boost reserve). */
    inner?: number | null;
    innerLabel?: string;
    tone?: "accent" | "warn" | "bad" | "good" | "nav";
    tickFormat?: (v: number) => string;
  } = $props();

  const CX = 100;
  const CY = 98;
  const R = 78;
  const START = 150;
  const SWEEP = 240;

  function pt(angle: number, r: number): [number, number] {
    const a = (angle * Math.PI) / 180;
    return [CX + r * Math.cos(a), CY + r * Math.sin(a)];
  }
  function arc(r: number): string {
    const [x1, y1] = pt(START, r);
    const [x2, y2] = pt(START + SWEEP, r);
    return `M${x1.toFixed(2)} ${y1.toFixed(2)} A${r} ${r} 0 1 1 ${x2.toFixed(2)} ${y2.toFixed(2)}`;
  }
  const clamp01 = (v: number) => Math.max(0, Math.min(1, v));
  const frac = $derived(value == null || !(max > 0) ? 0 : clamp01(value / max));

  const majors = $derived(Array.from({ length: ticks + 1 }, (_, i) => i / ticks));
  const minors = $derived(
    Array.from({ length: ticks * 4 + 1 }, (_, i) => i / (ticks * 4)).filter((_, i) => i % 4 !== 0),
  );
  const peakAngle = $derived(peak != null && peak > 0 && max > 0 ? START + SWEEP * clamp01(peak / max) : null);
  const tip = $derived(pt(START + SWEEP * frac, R));
</script>

<svg viewBox="0 0 200 176" class="gauge {tone}" role="img" aria-label="{caption} {display} {unit}">
  <path class="track" d={arc(R)} pathLength="100" />
  <path class="value" d={arc(R)} pathLength="100" stroke-dasharray="{frac * 100} 100" />
  {#if value != null && frac > 0.002}
    <circle class="tip" cx={tip[0]} cy={tip[1]} r="5.5" />
  {/if}
  {#if inner !== null}
    <path class="track thin" d={arc(R - 14)} pathLength="100" />
    <path class="inner" d={arc(R - 14)} pathLength="100" stroke-dasharray="{clamp01(inner) * 100} 100" />
  {/if}
  {#each minors as f (f)}
    {@const [x1, y1] = pt(START + SWEEP * f, R + 8)}
    {@const [x2, y2] = pt(START + SWEEP * f, R + 11)}
    <line class="tick minor" {x1} {y1} {x2} {y2} />
  {/each}
  {#each majors as f (f)}
    {@const [x1, y1] = pt(START + SWEEP * f, R + 7)}
    {@const [x2, y2] = pt(START + SWEEP * f, R + 14)}
    {@const [tx, ty] = pt(START + SWEEP * f, R - (inner !== null ? 29 : 19))}
    <line class="tick" {x1} {y1} {x2} {y2} />
    <text class="tl" x={tx} y={ty}>{tickFormat(f * max)}</text>
  {/each}
  {#if peakAngle !== null}
    {@const [px, py] = pt(peakAngle, R + 4)}
    {@const [qx, qy] = pt(peakAngle - 3.5, R + 15)}
    {@const [rx, ry] = pt(peakAngle + 3.5, R + 15)}
    <path class="peak" d="M{px} {py} L{qx} {qy} L{rx} {ry} Z"><title>Peak in the last 3 minutes</title></path>
  {/if}
  <text class="big num display" x={CX} y={CY + 8}>{display}</text>
  <text class="unit" x={CX} y={CY + 27}>{unit}</text>
  {#if caption}<text class="caption" x={CX} y={CY + 58}>{caption}</text>{/if}
  {#if innerLabel}<text class="innerlabel" x={CX} y={CY + 73}>{innerLabel}</text>{/if}
</svg>

<style>
  .gauge {
    width: 100%;
    height: auto;
    display: block;
    overflow: visible;
    --c: var(--accent);
  }
  .warn {
    --c: var(--warn);
  }
  .bad {
    --c: var(--bad);
  }
  .good {
    --c: var(--good);
  }
  .nav {
    --c: var(--nav);
  }
  path {
    fill: none;
    stroke-linecap: round;
  }
  .track {
    stroke: var(--line);
    stroke-width: 10;
  }
  .track.thin {
    stroke-width: 4;
  }
  .value {
    stroke: var(--c);
    stroke-width: 10;
    filter: drop-shadow(0 0 var(--glow, 6px) color-mix(in srgb, var(--c) 60%, transparent));
    transition: stroke-dasharray 0.18s linear;
  }
  .tip {
    fill: var(--text);
    stroke: var(--c);
    stroke-width: 2;
    filter: drop-shadow(0 0 var(--glow, 6px) var(--c));
  }
  .inner {
    stroke: color-mix(in srgb, var(--c) 45%, var(--text));
    stroke-width: 4;
    transition: stroke-dasharray 0.3s linear;
  }
  .tick {
    stroke: var(--text-3);
    stroke-width: 1.6;
  }
  .tick.minor {
    stroke: var(--line-2);
    stroke-width: 1;
  }
  .tl {
    fill: var(--text-3);
    font-size: 9px;
    font-family: var(--mono);
    text-anchor: middle;
    dominant-baseline: middle;
  }
  .peak {
    fill: var(--text-2);
    stroke: none;
  }
  text {
    text-anchor: middle;
  }
  .big {
    fill: var(--text);
    font-size: 42px;
    font-weight: 700;
    letter-spacing: -0.02em;
    font-family: var(--font);
  }
  .unit {
    fill: var(--text-3);
    font-size: 10.5px;
    font-weight: 600;
    letter-spacing: 0.14em;
  }
  .caption {
    fill: var(--c);
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 0.24em;
    font-family: var(--mono);
  }
  .innerlabel {
    fill: var(--text-3);
    font-size: 8.5px;
    letter-spacing: 0.14em;
  }
</style>
