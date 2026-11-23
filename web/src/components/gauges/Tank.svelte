<script lang="ts">
  import { pct } from "../../lib/format";

  // A vertical tank for a 0-1 level.
  let {
    value,
    label,
    note = "No data",
    tone = "auto",
    active = false,
  }: { value: number | null; label: string; note?: string; tone?: "auto" | "accent"; active?: boolean } =
    $props();

  const level = $derived(value == null ? null : Math.max(0, Math.min(1, value)));
  const color = $derived(
    level == null ? "muted" : tone === "accent" ? "accent" : level < 0.1 ? "bad" : level < 0.25 ? "warn" : "good",
  );
</script>

<div
  class="tank {color}"
  class:active
  role="meter"
  aria-label={label}
  aria-valuenow={level ?? undefined}
  aria-valuemin={0}
  aria-valuemax={1}
>
  <div class="glass">
    <div class="fill" style:height="{(level ?? 0) * 100}%"></div>
    {#each [0.25, 0.5, 0.75] as m (m)}<span class="mark" style:bottom="{m * 100}%"></span>{/each}
  </div>
  <span class="v num">{level == null ? note : pct(level)}</span>
  <span class="label">{label}</span>
</div>

<style>
  .tank {
    display: grid;
    justify-items: center;
    align-content: start;
    gap: 7px;
    min-width: 0;
    --c: var(--good);
  }
  .warn {
    --c: var(--warn);
  }
  .bad {
    --c: var(--bad);
  }
  .accent {
    --c: var(--accent);
  }
  .glass {
    position: relative;
    width: 36px;
    height: var(--tank-h, 116px);
    border-radius: 10px;
    border: 1px solid var(--line-2);
    background: var(--bg-2);
    overflow: hidden;
  }
  .muted .glass {
    background: repeating-linear-gradient(-45deg, var(--bg-2) 0 6px, var(--panel-2) 6px 12px);
  }
  .fill {
    position: absolute;
    inset: auto 0 0 0;
    background: linear-gradient(0deg, color-mix(in srgb, var(--c) 45%, transparent), var(--c));
    box-shadow: 0 0 14px color-mix(in srgb, var(--c) 45%, transparent);
    transition: height 0.4s ease;
  }
  .fill::after {
    content: "";
    position: absolute;
    inset: 0 0 auto 0;
    height: 2px;
    background: #ffffff88;
  }
  .active .fill {
    animation: pulse 0.8s ease-in-out infinite;
  }
  .mark {
    position: absolute;
    left: 0;
    width: 8px;
    height: 1px;
    background: var(--text-3);
    opacity: 0.6;
  }
  .v {
    font-weight: 700;
    font-size: 0.95rem;
    text-align: center;
  }
  .muted .v {
    color: var(--text-3);
    font-weight: 500;
    font-size: 0.74rem;
  }
  .label {
    text-align: center;
  }
</style>
