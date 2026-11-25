<script lang="ts">
  // A small arc gauge: a label, the arc, the number in it. Two kinds:
  //   from zero (G: filled from 0, with a peak marker and a danger zone), or
  //   centred (climb rate: a needle either side of zero, up good, down warn).
  // `frac` is where the value sits, 0..1 (centred: -1..1); the caller scales it.
  let {
    label,
    display,
    unit = "",
    frac,
    centred = false,
    peak = null,
    danger = null,
    tone = "accent",
  }: {
    label: string;
    display: string;
    unit?: string;
    frac: number | null;
    centred?: boolean;
    /** 0..1: the highest so far (a small marker). */
    peak?: number | null;
    /** 0..1: where the danger band starts. */
    danger?: number | null;
    tone?: "accent" | "good" | "warn" | "bad";
  } = $props();

  const CX = 50;
  const CY = 46;
  const R = 36;
  const A = 115; // degrees either side of straight up
  const rad = (d: number) => (d * Math.PI) / 180;
  const pt = (a: number, r = R) => [CX + r * Math.sin(rad(a)), CY - r * Math.cos(rad(a))] as const;
  function arc(a0: number, a1: number): string {
    if (Math.abs(a1 - a0) < 0.5) return "";
    const [lo, hi] = a0 < a1 ? [a0, a1] : [a1, a0];
    const [x0, y0] = pt(lo);
    const [x1, y1] = pt(hi);
    return `M${x0.toFixed(1)} ${y0.toFixed(1)} A${R} ${R} 0 ${hi - lo > 180 ? 1 : 0} 1 ${x1.toFixed(1)} ${y1.toFixed(1)}`;
  }
  const clamp = (v: number, a: number, b: number) => Math.max(a, Math.min(b, v));
  const angle = $derived(
    frac == null ? null : centred ? clamp(frac, -1, 1) * A : -A + clamp(frac, 0, 1) * 2 * A,
  );
  const valueArc = $derived(angle == null ? "" : centred ? arc(0, angle) : arc(-A, angle));
  const needle = $derived(angle == null || !centred ? null : pt(angle, R - 4));
  const peakAt = $derived(peak == null || centred ? null : pt(-A + clamp(peak, 0, 1) * 2 * A, R + 6));
  const peakAngle = $derived(peak == null ? 0 : -A + clamp(peak, 0, 1) * 2 * A);
</script>

<div class="mini {tone}">
  <span class="label">{label}</span>
  <div class="row">
    <svg viewBox="0 0 100 56" aria-hidden="true">
      <path d={arc(-A, A)} class="track" />
      {#if danger != null && !centred}<path d={arc(-A + clamp(danger, 0, 1) * 2 * A, A)} class="danger" />{/if}
      {#if centred}<line x1={CX} y1={CY - R - 5} x2={CX} y2={CY - R + 5} class="zero" />{/if}
      {#if valueArc}<path d={valueArc} class="value" />{/if}
      {#if needle}<line x1={CX} y1={CY} x2={needle[0]} y2={needle[1]} class="needle" /><circle
          cx={CX}
          cy={CY}
          r="3"
          class="hub"
        />{/if}
      {#if peakAt}<polygon
          points="{peakAt[0]},{peakAt[1]} {peakAt[0] - 4},{peakAt[1] - 7} {peakAt[0] + 4},{peakAt[1] - 7}"
          transform="rotate({peakAngle + 180} {peakAt[0]} {peakAt[1]})"
          class="peak"
        />{/if}
    </svg>
    <span class="v num" role="img" aria-label="{label} {display} {unit}">{display}{#if unit}<small>{unit}</small>{/if}</span>
  </div>
</div>

<style>
  .mini {
    display: grid;
    gap: 0;
    min-width: 0;
    --c: var(--accent);
  }
  .good {
    --c: var(--good);
  }
  .warn {
    --c: var(--warn);
  }
  .bad {
    --c: var(--bad);
  }
  .row {
    display: flex;
    align-items: center;
    gap: 6px;
    min-width: 0;
  }
  svg {
    height: 50px;
    width: auto;
    flex: none;
    overflow: visible;
  }
  .track {
    fill: none;
    stroke: var(--line);
    stroke-width: var(--gs-mini-w, 6);
    stroke-linecap: var(--gs-mini-cap, round);
    stroke-dasharray: var(--gs-mini-dash, none);
  }
  .danger {
    fill: none;
    stroke: var(--bad);
    stroke-width: 6;
    opacity: 0.35;
  }
  .value {
    fill: none;
    stroke: var(--c);
    stroke-width: var(--gs-mini-w, 6);
    stroke-linecap: var(--gs-mini-cap, round);
    stroke-dasharray: var(--gs-mini-dash, none);
    transition: d 0.15s linear;
  }
  .zero {
    stroke: var(--text-3);
    stroke-width: 1.5;
  }
  .needle {
    stroke: var(--c);
    stroke-width: 2.4;
    stroke-linecap: round;
  }
  .hub {
    fill: var(--text-2);
  }
  .peak {
    fill: var(--accent-2, var(--accent));
  }
  .v {
    font-size: 1.3rem;
    font-weight: 700;
    line-height: 1.1;
    color: var(--text);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .v small {
    font-size: 0.55em;
    color: var(--text-3);
    margin-left: 2px;
    font-weight: 600;
  }
</style>
