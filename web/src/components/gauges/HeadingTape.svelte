<script lang="ts">
  // A scrolling compass tape centred on the heading.
  let {
    heading,
    compact = false,
    note = "No heading",
  }: { heading: number | null; compact?: boolean; note?: string } = $props();

  const PX = $derived(compact ? 3.5 : 5); // pixels per degree
  const SPAN = 130; // degrees drawn each side: wider than any panel
  const CARDINAL: Record<number, string> = {
    0: "N",
    45: "NE",
    90: "E",
    135: "SE",
    180: "S",
    225: "SW",
    270: "W",
    315: "NW",
  };

  const h = $derived(heading == null ? null : ((heading % 360) + 360) % 360);
  const ticks = $derived.by(() => {
    if (h == null) return [];
    const out: { d: number; off: number; deg: number; kind: "label" | "major" | "minor" }[] = [];
    const start = Math.ceil((h - SPAN) / 5) * 5;
    for (let d = start; d <= h + SPAN; d += 5) {
      const deg = ((d % 360) + 360) % 360;
      const kind = deg % 15 === 0 ? "label" : deg % 10 === 0 ? "major" : "minor";
      out.push({ d, off: (d - h) * PX, deg, kind });
    }
    return out;
  });
  const label = (deg: number) => CARDINAL[deg] ?? String(deg).padStart(3, "0");
</script>

<div class="tape" class:none={h == null} class:compact>
  {#if h == null}
    <span class="nodata" title="The game only reports heading near a planet">{note}</span>
  {:else}
    {#each ticks as t (t.d)}
      <span class="tick {t.kind}" class:card={t.deg in CARDINAL} style:transform="translateX({t.off}px)">
        {#if t.kind === "label" && Math.abs(t.off) > 34}<b>{label(t.deg)}</b>{/if}
      </span>
    {/each}
    <div class="caret">
      <span class="num">{String(Math.round(h) % 360).padStart(3, "0")}°</span>
    </div>
  {/if}
</div>

<style>
  .tape {
    position: relative;
    height: 46px;
    overflow: hidden;
    mask-image: linear-gradient(90deg, transparent, #000 12%, #000 88%, transparent);
  }
  .tape.compact {
    height: 42px;
  }
  .none {
    display: grid;
    place-items: center;
    /* a dimmed, empty tape */
    background: repeating-linear-gradient(90deg, var(--line) 0 1px, transparent 1px 25px) bottom / 100% 8px no-repeat;
  }
  .nodata {
    color: var(--text-3);
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    padding: 2px 8px;
    border: 1px solid var(--line-2);
    border-radius: 2px;
    background: var(--panel);
  }
  .tick {
    position: absolute;
    left: 50%;
    bottom: 0;
    width: 1px;
    height: 8px;
    background: var(--line-2);
  }
  .tick.major {
    height: 13px;
    background: var(--text-3);
  }
  .tick.label {
    height: 14px;
    background: var(--text-2);
  }
  .tick b {
    position: absolute;
    bottom: 17px;
    left: 50%;
    transform: translateX(-50%);
    font-family: var(--mono);
    font-size: 0.74rem;
    font-weight: 600;
    color: var(--text-2);
  }
  .tick.card b {
    color: var(--accent);
    font-weight: 800;
    font-size: 0.86rem;
  }
  .caret {
    position: absolute;
    left: 50%;
    top: 0;
    transform: translateX(-50%);
    display: grid;
    justify-items: center;
    z-index: 1;
  }
  .caret span {
    font-weight: 800;
    font-size: 0.9rem;
    padding: 0 8px;
    border-radius: 2px;
    color: var(--bg);
    background: var(--accent);
    box-shadow: 0 0 var(--glow, 14px) color-mix(in srgb, var(--accent) 55%, transparent);
  }
  .caret::after {
    content: "";
    width: 2px;
    height: 30px;
    background: var(--accent);
    box-shadow: 0 0 8px var(--accent);
  }
</style>
