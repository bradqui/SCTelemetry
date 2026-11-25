<script lang="ts">
  import { onMount, untrack } from "svelte";
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
  const angle = $derived(START + SWEEP * frac);
  const uid = $props.id();

  // Instrument styles (themes.ts GaugeStyle): every layer is drawn; the theme's CSS
  // variables show one. Pieces the styles share are computed once here.
  function arcPart(r: number, f0: number, f1: number): string {
    const [x1, y1] = pt(START + SWEEP * f0, r);
    const [x2, y2] = pt(START + SWEEP * f1, r);
    const large = SWEEP * (f1 - f0) > 180 ? 1 : 0;
    return `M${x1.toFixed(2)} ${y1.toFixed(2)} A${r} ${r} 0 ${large} 1 ${x2.toFixed(2)} ${y2.toFixed(2)}`;
  }
  const SEGMENTS = 30;
  const segs = $derived(
    Array.from({ length: SEGMENTS }, (_, i) => ({
      d: arcPart(R, i / SEGMENTS + 0.006, (i + 1) / SEGMENTS - 0.006),
      lit: i < Math.round(frac * SEGMENTS),
    })),
  );
  const innerSegs = $derived(
    inner == null
      ? []
      : Array.from({ length: 15 }, (_, i) => ({
          d: arcPart(R - 15, i / 15 + 0.01, (i + 1) / 15 - 0.01),
          lit: i < Math.round(clamp01(inner) * 15),
        })),
  );
  const needle = $derived(pt(angle, R - 16));
  // The analog bezel: a heavy ring, open at the bottom where the readout sits.
  const bezel = (() => {
    const r = R + 8;
    const [x1, y1] = pt(START - 18, r);
    const [x2, y2] = pt(START + SWEEP + 18, r);
    return `M${x1.toFixed(2)} ${y1.toFixed(2)} A${r} ${r} 0 1 1 ${x2.toFixed(2)} ${y2.toFixed(2)}`;
  })();
  const chevron = $derived.by(() => {
    const [tx, ty] = pt(angle, R + 3);
    const [lx, ly] = pt(angle - 4, R + 15);
    const [rx, ry] = pt(angle + 4, R + 15);
    return `M${tx.toFixed(1)} ${ty.toFixed(1)} L${lx.toFixed(1)} ${ly.toFixed(1)} L${rx.toFixed(1)} ${ry.toFixed(1)} Z`;
  });
  const BR = R + 20; // angular brackets
  const brackets = [
    [-1, -1],
    [1, -1],
    [-1, 1],
    [1, 1],
  ].map(([sx, sy]) => {
    const x = CX + sx * BR;
    const y = sy < 0 ? CY - BR : CY + 72; // the bottom pair stays inside the dial's box
    return `M${x - sx * 18} ${y} L${x} ${y} L${x} ${y - sy * 18}`;
  });

  // The big number shrinks to fit between the side tick labels (1,399 m/s, 5,040 km/h,
  // a wide theme font). Room: twice the gap from the centre to the inner edge of the
  // labels at 20% / 80%, less a margin.
  const BIG = 42;
  const labelR = $derived(R - (inner !== null ? 29 : 19));
  const room = $derived(2 * (labelR * Math.cos((18 * Math.PI) / 180) - 13));
  let bigEl = $state<SVGTextElement>();
  let fit = $state(1);
  function measure() {
    if (!bigEl) return;
    const natural = bigEl.getComputedTextLength() / untrack(() => fit);
    const next = natural > room ? room / natural : 1;
    if (Math.abs(next - untrack(() => fit)) > 0.005) fit = next;
  }
  $effect(() => {
    void display; // every new value (and its width)
    void room;
    measure();
  });
  onMount(() => {
    // Theme fonts arrive late: measure again once they have.
    document.fonts?.addEventListener("loadingdone", measure);
    return () => document.fonts?.removeEventListener("loadingdone", measure);
  });
  // Smaller text stays centred where the full-size number was.
  const bigSize = $derived(BIG * fit);
  const bigY = $derived(CY - 7 + 0.36 * bigSize);
</script>

<svg viewBox="0 0 200 176" class="gauge {tone}" role="img" aria-label="{caption} {display} {unit}">
  <g class="layer standard">
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
  </g>

  <!-- Glass (Origin): thin arcs and a dot, nothing more. -->
  <g class="layer glass">
    <path class="g-track" d={arc(R)} />
    <path class="g-value" d={arc(R)} pathLength="100" stroke-dasharray="{frac * 100} 100" />
    {#if value != null && frac > 0.002}<circle class="g-tip" cx={tip[0]} cy={tip[1]} r="4" />{/if}
    {#if inner !== null}
      <path class="g-inner-track" d={arc(R - 13)} />
      <path class="g-inner" d={arc(R - 13)} pathLength="100" stroke-dasharray="{clamp01(inner) * 100} 100" />
    {/if}
    {#each majors as f (f)}
      {@const [tx, ty] = pt(START + SWEEP * f, R - (inner !== null ? 27 : 17))}
      <text class="tl" x={tx} y={ty}>{tickFormat(f * max)}</text>
    {/each}
  </g>

  <!-- Analog (Drake): a bezel, a needle and a hazard band at the top of the scale. -->
  <g class="layer analog">
    <defs>
      <pattern id="hz-{uid}" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
        <rect width="7" height="7" class="a-hz-bg" /><rect width="3.5" height="7" class="a-hz" />
      </pattern>
    </defs>
    <path class="a-bezel" d={bezel} />
    <path d={arcPart(R - 2, 0.8, 1)} class="a-band" stroke="url(#hz-{uid})" />
    {#each minors as f (f)}
      {@const [x1, y1] = pt(START + SWEEP * f, R - 7)}
      {@const [x2, y2] = pt(START + SWEEP * f, R)}
      <line class="a-tick minor" {x1} {y1} {x2} {y2} />
    {/each}
    {#each majors as f (f)}
      {@const [x1, y1] = pt(START + SWEEP * f, R - 13)}
      {@const [x2, y2] = pt(START + SWEEP * f, R)}
      {@const [tx, ty] = pt(START + SWEEP * f, R - 23)}
      <line class="a-tick" {x1} {y1} {x2} {y2} />
      <text class="tl" x={tx} y={ty}>{tickFormat(f * max)}</text>
    {/each}
    {#if inner !== null}
      <path class="a-inner-track" d={arc(R - 33)} />
      <path class="a-inner" d={arc(R - 33)} pathLength="100" stroke-dasharray="{clamp01(inner) * 100} 100" />
    {/if}
    {#if value != null}
      <line class="a-needle" x1={CX} y1={CY} x2={needle[0]} y2={needle[1]} />
    {/if}
    <circle class="a-hub" cx={CX} cy={CY} r="6.5" />
  </g>

  <!-- Segmented (Aegis): lit segments, like a military display. -->
  <g class="layer segmented">
    {#each segs as sg, i (i)}<path d={sg.d} class="s-seg" class:lit={sg.lit} />{/each}
    {#each innerSegs as sg, i (i)}<path d={sg.d} class="s-iseg" class:lit={sg.lit} />{/each}
    {#each majors as f (f)}
      {@const [tx, ty] = pt(START + SWEEP * f, R - (inner !== null ? 29 : 19))}
      <text class="tl" x={tx} y={ty}>{tickFormat(f * max)}</text>
    {/each}
  </g>

  <!-- Angular (Anvil): corner brackets, square ends and a chevron pointer. -->
  <g class="layer angular">
    {#each brackets as d, i (i)}<path {d} class="n-bracket" />{/each}
    <path class="n-track" d={arc(R - 3)} />
    <path class="n-value" d={arc(R - 3)} pathLength="100" stroke-dasharray="{frac * 100} 100" />
    {#each majors as f (f)}
      {@const [x1, y1] = pt(START + SWEEP * f, R + 2)}
      {@const [x2, y2] = pt(START + SWEEP * f, R + 9)}
      {@const [tx, ty] = pt(START + SWEEP * f, R - (inner !== null ? 29 : 19))}
      <line class="n-tick" {x1} {y1} {x2} {y2} />
      <text class="tl" x={tx} y={ty}>{tickFormat(f * max)}</text>
    {/each}
    {#if inner !== null}
      <path class="n-inner-track" d={arc(R - 15)} />
      <path class="n-inner" d={arc(R - 15)} pathLength="100" stroke-dasharray="{clamp01(inner) * 100} 100" />
    {/if}
    {#if value != null && frac > 0.002}<path class="n-chevron" d={chevron} />{/if}
  </g>

  <g class="readout">
    <text class="big num display" x={CX} y={bigY} style:font-size="{bigSize}px" bind:this={bigEl}>{display}</text>
    <text class="unit" x={CX} y={CY + 27}>{unit}</text>
  </g>
  <g class="captions">
    {#if caption}<text class="caption" x={CX} y={CY + 58}>{caption}</text>{/if}
    {#if innerLabel}<text class="innerlabel" x={CX} y={CY + 73}>{innerLabel}</text>{/if}
  </g>
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
  /* Instrument styles: the theme shows one layer (themes.ts sets --gs-<style>). */
  .layer.standard {
    display: var(--gs-standard, inline);
  }
  .layer.glass {
    display: var(--gs-glass, none);
  }
  .layer.analog {
    display: var(--gs-analog, none);
  }
  .layer.segmented {
    display: var(--gs-segmented, none);
  }
  .layer.angular {
    display: var(--gs-angular, none);
  }
  /* Analog: the hub sits where the number would, so the readout drops below it. */
  .readout,
  .captions {
    transform-box: view-box;
    transform-origin: 100px 98px;
    transform: translateY(var(--gs-num-dy, 0px)) scale(var(--gs-num-scale, 1));
  }
  .captions {
    transform: translateY(var(--gs-cap-dy, 0px));
  }
  .g-track {
    stroke: var(--line-2);
    stroke-width: 2;
  }
  .g-value {
    stroke: var(--c);
    stroke-width: 3.5;
    transition: stroke-dasharray 0.18s linear;
  }
  .g-tip {
    fill: var(--c);
  }
  .g-inner-track {
    stroke: var(--line);
    stroke-width: 1.5;
  }
  .g-inner {
    stroke: var(--text-2);
    stroke-width: 2;
    transition: stroke-dasharray 0.3s linear;
  }
  .a-bezel {
    fill: none;
    stroke: var(--line-2);
    stroke-width: 6;
    stroke-linecap: round;
  }
  .a-band {
    stroke-width: 7;
    stroke-linecap: butt;
    opacity: 0.85;
  }
  .a-hz-bg {
    fill: var(--stripe-2, var(--bg-2));
  }
  .a-hz {
    fill: var(--stripe, var(--warn));
  }
  .a-tick {
    stroke: var(--text);
    stroke-width: 2.6;
  }
  .a-tick.minor {
    stroke: var(--text-2);
    stroke-width: 1.3;
  }
  .a-needle {
    stroke: var(--c);
    stroke-width: 4;
    stroke-linecap: round;
    filter: drop-shadow(0 0 3px color-mix(in srgb, var(--c) 50%, transparent));
  }
  .a-hub {
    fill: var(--panel-2);
    stroke: var(--c);
    stroke-width: 2.5;
  }
  .a-inner-track {
    stroke: var(--line);
    stroke-width: 3;
  }
  .a-inner {
    stroke: color-mix(in srgb, var(--c) 40%, var(--text));
    stroke-width: 3;
    transition: stroke-dasharray 0.3s linear;
  }
  .s-seg {
    stroke: var(--line);
    stroke-width: 11;
    stroke-linecap: butt;
  }
  .s-seg.lit {
    stroke: var(--c);
    filter: drop-shadow(0 0 3px color-mix(in srgb, var(--c) 70%, transparent));
  }
  .s-iseg {
    stroke: var(--line);
    stroke-width: 4;
    stroke-linecap: butt;
  }
  .s-iseg.lit {
    stroke: color-mix(in srgb, var(--c) 60%, var(--text));
  }
  .n-bracket {
    stroke: var(--line-2);
    stroke-width: 3;
    stroke-linecap: square;
  }
  .n-track {
    stroke: var(--line);
    stroke-width: 6;
    stroke-linecap: butt;
  }
  .n-value {
    stroke: var(--c);
    stroke-width: 6;
    stroke-linecap: butt;
    transition: stroke-dasharray 0.18s linear;
  }
  .n-tick {
    stroke: var(--text-3);
    stroke-width: 2;
  }
  .n-inner-track {
    stroke: var(--line);
    stroke-width: 3;
    stroke-linecap: butt;
  }
  .n-inner {
    stroke: color-mix(in srgb, var(--c) 45%, var(--text));
    stroke-width: 3;
    stroke-linecap: butt;
    transition: stroke-dasharray 0.3s linear;
  }
  .n-chevron {
    fill: var(--c);
    stroke: none;
  }
</style>
