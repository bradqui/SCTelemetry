<script lang="ts">
  import { WINDOW_S, type Sample } from "../../lib/trends.svelte";

  // One series over the trend window, with a hover crosshair and readout.
  let {
    samples,
    pick,
    label,
    format,
    unit = "",
    zero = true,
    height = 70,
  }: {
    samples: Sample[];
    pick: (s: Sample) => number | null;
    label: string;
    format: (v: number) => string;
    unit?: string;
    /** Scale starts at zero (speed, G) rather than fitting the data (altitude). */
    zero?: boolean;
    height?: number;
  } = $props();

  let width = $state(300);
  let hover = $state<number | null>(null);
  const PAD_T = 6;
  const PAD_B = 4;

  const end = $derived(samples.length ? samples[samples.length - 1].t : 0);
  // The window grows with the data (at least 30 s) up to the full trend window.
  const start = $derived(
    samples.length ? Math.min(Math.max(samples[0].t, end - WINDOW_S * 1000), end - 30_000) : 0,
  );
  const values = $derived(samples.map(pick));
  const extent = $derived.by(() => {
    let lo = Infinity;
    let hi = -Infinity;
    for (const v of values) {
      if (v == null) continue;
      if (v < lo) lo = v;
      if (v > hi) hi = v;
    }
    if (hi === -Infinity) return null;
    if (zero) lo = Math.min(0, lo);
    if (hi - lo < 1e-6) hi = lo + 1;
    return [lo, hi] as const;
  });

  const x = (t: number) => ((t - start) / (end - start || 1)) * width;
  const y = (v: number) =>
    extent ? PAD_T + (1 - (v - extent[0]) / (extent[1] - extent[0])) * (height - PAD_T - PAD_B) : height;

  // Line and area paths, broken where there is no value (e.g. altitude in space).
  const paths = $derived.by(() => {
    let line = "";
    let area = "";
    let run: [number, number][] = [];
    const flush = () => {
      if (run.length > 1) {
        line += "M" + run.map(([a, b]) => `${a.toFixed(1)} ${b.toFixed(1)}`).join("L");
        area += `M${run[0][0].toFixed(1)} ${height}L` + run.map(([a, b]) => `${a.toFixed(1)} ${b.toFixed(1)}`).join("L") + `L${run[run.length - 1][0].toFixed(1)} ${height}Z`;
      }
      run = [];
    };
    samples.forEach((s, i) => {
      const v = values[i];
      if (v == null) flush();
      else run.push([x(s.t), y(v)]);
    });
    flush();
    return { line, area };
  });

  const current = $derived.by(() => {
    for (let i = values.length - 1; i >= 0; i--) if (values[i] != null) return values[i];
    return null;
  });

  function onMove(e: PointerEvent) {
    if (!samples.length) return;
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    const t = start + ((e.clientX - rect.left) / rect.width) * (end - start);
    let best = 0;
    for (let i = 1; i < samples.length; i++) {
      if (Math.abs(samples[i].t - t) < Math.abs(samples[best].t - t)) best = i;
    }
    hover = best;
  }

  const hv = $derived(hover != null && hover < samples.length ? values[hover] : null);
  const hx = $derived(hover != null && hover < samples.length ? x(samples[hover].t) : 0);
</script>

<div class="spark">
  <div class="head">
    <span class="label">{label}</span>
    <span class="now num">{current == null ? "—" : format(current)}<small>{unit}</small></span>
  </div>
  <div
    class="plot"
    style:height="{height}px"
    bind:clientWidth={width}
    onpointermove={onMove}
    onpointerleave={() => (hover = null)}
    role="img"
    aria-label="{label} over the last {WINDOW_S / 60} minutes"
  >
    <svg {width} {height} aria-hidden="true">
      <line class="grid" x1="0" x2={width} y1={PAD_T} y2={PAD_T} />
      <line class="grid" x1="0" x2={width} y1={(height + PAD_T) / 2} y2={(height + PAD_T) / 2} />
      <line class="base" x1="0" x2={width} y1={height - 0.5} y2={height - 0.5} />
      <path class="area" d={paths.area} />
      <path class="line" d={paths.line} />
      {#if hover != null && hv != null}
        <line class="cross" x1={hx} x2={hx} y1="0" y2={height} />
        <circle class="dot" cx={hx} cy={y(hv)} r="4" />
      {/if}
    </svg>
    {#if extent}<span class="max num">{format(extent[1])}</span>{/if}
    {#if hover != null && hover < samples.length}
      <span class="tip num" style:left="{Math.min(Math.max(hx, 50), width - 50)}px">
        {hv == null ? "no data" : `${format(hv)} ${unit}`} · {Math.round((end - samples[hover].t) / 1000)}s ago
      </span>
    {/if}
  </div>
</div>

<style>
  .spark {
    display: grid;
    gap: 6px;
    min-width: 0;
  }
  .head {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
  }
  .now {
    font-weight: 700;
    font-size: 1.05rem;
  }
  .now small {
    font-size: 0.7rem;
    color: var(--text-3);
    margin-left: 4px;
    font-weight: 600;
  }
  .plot {
    position: relative;
    cursor: crosshair;
    touch-action: pan-y;
  }
  svg {
    display: block;
    overflow: visible;
  }
  .grid {
    stroke: var(--line);
    stroke-dasharray: 2 4;
  }
  .base {
    stroke: var(--line-2);
  }
  .area {
    fill: color-mix(in srgb, var(--accent) 14%, transparent);
  }
  .line {
    fill: none;
    stroke: var(--accent);
    stroke-width: 2;
    stroke-linejoin: round;
    filter: drop-shadow(0 0 3px color-mix(in srgb, var(--accent) 50%, transparent));
  }
  .cross {
    stroke: var(--text-3);
  }
  .dot {
    fill: var(--accent);
    stroke: var(--panel);
    stroke-width: 2;
  }
  .max {
    position: absolute;
    top: -2px;
    left: 2px;
    font-size: 0.66rem;
    color: var(--text-3);
    pointer-events: none;
  }
  .tip {
    position: absolute;
    top: -26px;
    transform: translateX(-50%);
    white-space: nowrap;
    font-size: 0.74rem;
    padding: 3px 8px;
    border-radius: 6px;
    background: var(--bg);
    border: 1px solid var(--line-2);
    color: var(--text);
    pointer-events: none;
    z-index: 2;
  }
</style>
