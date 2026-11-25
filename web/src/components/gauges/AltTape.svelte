<script lang="ts">
  import { altitude } from "../../lib/format";

  // A slim vertical altitude tape: the scale moves past a fixed pointer, and the ground is
  // hatched in when it's within the window (from the height above ground the game sends).
  // In space (no altitude) it says so. Fills its box's height; about 60 px wide.
  let { alt, agl }: { alt: number | null; agl: number | null } = $props();

  const uid = $props.id();
  const H = 200;
  const W = 60;
  const MID = H / 2;

  // Step between labels, by how high you are: 100 m low down, 1 km, then 10 km.
  const step = $derived(alt == null ? 100 : alt < 1500 ? 100 : alt < 15_000 ? 1000 : 10_000);
  const span = $derived(step * 8); // metres shown top to bottom (taller tape, more scale)
  const y = (m: number) => MID - ((m - (alt ?? 0)) / span) * H;
  const label = (m: number) => (step >= 1000 ? `${m / 1000}k` : String(m));

  const ticks = $derived.by(() => {
    if (alt == null) return [];
    const minor = step / 2;
    const out: { y: number; major: boolean; text: string }[] = [];
    for (let m = Math.ceil((alt - span / 2) / minor) * minor; m <= alt + span / 2; m += minor) {
      const yy = y(m);
      if (yy < 4 || yy > H - 4 || m < 0) continue;
      const major = Math.round(m / step) * step === m;
      out.push({ y: yy, major, text: major ? label(m) : "" });
    }
    return out;
  });
  const groundY = $derived(alt != null && agl != null ? y(alt - agl) : null);
  const shown = $derived(altitude(alt));
  const near = $derived(agl != null && agl < 50);
</script>

<div class="tape" role="img" aria-label={alt == null ? "Altitude: in space" : `Altitude ${shown.value} ${shown.unit}${agl != null ? `, ${Math.round(agl)} m above ground` : ""}`}>
  <svg viewBox="0 0 {W} {H}" preserveAspectRatio="none" aria-hidden="true">
    <defs>
      <pattern id="ground-{uid}" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
        <line x1="0" y1="0" x2="0" y2="5" class="hatch" />
      </pattern>
      <clipPath id="clip-{uid}"><rect x="0" y="2" width={W} height={H - 4} /></clipPath>
    </defs>
    <g clip-path="url(#clip-{uid})">
      {#if groundY != null && groundY < H}
        <rect x="0" y={Math.max(2, groundY)} width={W} height={H - Math.max(2, groundY)} fill="url(#ground-{uid})" />
        <line x1="0" x2={W} y1={groundY} y2={groundY} class="ground" />
      {/if}
      {#each ticks as t (t.y)}
        <line x1={W - (t.major ? 12 : 6)} x2={W} y1={t.y} y2={t.y} class="tick" class:major={t.major} />
      {/each}
    </g>
  </svg>
  <!-- Labels and the readout as HTML, so they don't stretch with the tape. -->
  {#each ticks as t (t.y)}
    {#if t.text}<span class="tl num" style:top="{(t.y / H) * 100}%">{t.text}</span>{/if}
  {/each}
  {#if alt == null}
    <span class="space">SPACE</span>
  {:else}
    <span class="now num" class:near>{shown.value}<small>{shown.unit}</small></span>
  {/if}
  <span class="agl num">AGL {agl == null ? "—" : `${Math.round(agl)}m`}</span>
</div>

<style>
  .tape {
    position: relative;
    height: 100%;
    min-height: 96px;
    width: 100%;
    border: 1px solid var(--line);
    border-radius: var(--radius-sm);
    background: color-mix(in srgb, var(--bg-2) 70%, transparent);
    overflow: hidden;
  }
  svg {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
  }
  .tick {
    stroke: var(--line-2);
    stroke-width: 1;
    vector-effect: non-scaling-stroke;
  }
  .tick.major {
    stroke: var(--text-3);
  }
  .hatch {
    stroke: var(--warn);
    stroke-width: 1.4;
    opacity: 0.45;
  }
  .ground {
    stroke: var(--warn);
    stroke-width: 1.5;
    vector-effect: non-scaling-stroke;
  }
  .tl {
    position: absolute;
    right: 14px;
    transform: translateY(-50%);
    font-size: 0.58rem;
    color: var(--text-3);
    line-height: 1;
    pointer-events: none;
  }
  .now {
    position: absolute;
    left: 2px;
    right: 2px;
    top: 50%;
    transform: translateY(-50%);
    padding: 2px 3px;
    text-align: center;
    font-size: 0.78rem;
    font-weight: 700;
    color: var(--text);
    background: var(--bg);
    border: 1px solid var(--accent);
    border-radius: var(--radius-chip);
    white-space: nowrap;
  }
  .now small {
    font-size: 0.7em;
    color: var(--text-3);
    margin-left: 1px;
  }
  .now.near {
    border-color: var(--warn);
  }
  .space {
    position: absolute;
    inset: 0;
    display: grid;
    place-items: center;
    writing-mode: vertical-rl;
    transform: rotate(180deg);
    font-size: 0.72rem;
    letter-spacing: 0.3em;
    color: var(--text-3);
  }
  .agl {
    position: absolute;
    left: 0;
    right: 0;
    bottom: 2px;
    text-align: center;
    font-size: 0.55rem;
    color: var(--text-3);
    background: linear-gradient(transparent, var(--bg-2) 45%);
    padding-top: 4px;
  }
</style>
