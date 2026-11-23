<script lang="ts">
  import { pct } from "../../lib/format";

  // A small donut for a 0-1 level, coloured by level.
  let { value, label }: { value: number | null; label: string } = $props();
  const level = $derived(value == null ? null : Math.max(0, Math.min(1, value)));
  const color = $derived(level == null ? "muted" : level < 0.25 ? "bad" : level < 0.5 ? "warn" : "good");
</script>

<div
  class="ring {color}"
  role="meter"
  aria-label={label}
  aria-valuenow={level ?? undefined}
  aria-valuemin={0}
  aria-valuemax={1}
>
  <div class="dial">
    <svg viewBox="0 0 64 64" aria-hidden="true">
      <circle class="track" cx="32" cy="32" r="26" />
      <circle class="fill" cx="32" cy="32" r="26" pathLength="100" stroke-dasharray="{(level ?? 0) * 100} 100" />
    </svg>
    <span class="v num">{level == null ? "—" : pct(level)}</span>
  </div>
  <span class="label">{label}</span>
</div>

<style>
  .ring {
    display: grid;
    justify-items: center;
    gap: 6px;
    min-width: 0;
    --c: var(--good);
  }
  .warn {
    --c: var(--warn);
  }
  .bad {
    --c: var(--bad);
  }
  .muted {
    --c: var(--line-2);
  }
  .dial {
    position: relative;
    width: min(100%, 84px);
    aspect-ratio: 1;
    display: grid;
    place-items: center;
  }
  svg {
    position: absolute;
    inset: 0;
    transform: rotate(-90deg);
  }
  circle {
    fill: none;
    stroke-width: 6;
  }
  .track {
    stroke: var(--line);
  }
  .fill {
    stroke: var(--c);
    stroke-linecap: round;
    filter: drop-shadow(0 0 4px color-mix(in srgb, var(--c) 50%, transparent));
    transition: stroke-dasharray 0.4s ease;
  }
  .v {
    font-weight: 700;
    font-size: 0.98rem;
  }
  .muted .v {
    color: var(--text-3);
  }
  .label {
    text-align: center;
  }
</style>
