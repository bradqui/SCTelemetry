<script lang="ts">
  let {
    label,
    value,
    unit = "",
    size = "md",
    tone = "",
  }: { label: string; value: string; unit?: string; size?: "xl" | "lg" | "md"; tone?: string } = $props();

  // Words like "SPACE" are shown smaller than numbers so they fit the column.
  const word = $derived(/^[A-Za-z]{3,}$/.test(value));
</script>

<div class="readout {size}">
  <span class="label">{label}</span>
  <span class="value num {tone}" class:word>{value}{#if unit}<span class="unit">{unit}</span>{/if}</span>
</div>

<style>
  .readout {
    display: grid;
    gap: 2px;
    min-width: 0;
  }
  .value {
    font-weight: 650;
    line-height: 1.05;
    letter-spacing: -0.01em;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .value.word {
    letter-spacing: 0.08em;
  }
  .md .value.word {
    font-size: 0.95rem;
    line-height: 1.75rem;
  }
  .lg .value.word {
    font-size: 1.15rem;
    line-height: clamp(1.9rem, 3.3vw, 2.6rem);
  }
  .xl .value.word {
    font-size: 1.6rem;
    line-height: clamp(2.8rem, 5.4vw, 4.6rem);
  }
  .xl .value {
    font-size: clamp(2.6rem, 5.2vw, 4.4rem);
    font-weight: 700;
  }
  .lg .value {
    font-size: clamp(1.7rem, 3vw, 2.4rem);
  }
  .md .value {
    font-size: 1.35rem;
  }
  .unit {
    font-size: 0.42em;
    font-weight: 600;
    color: var(--text-3);
    margin-left: 0.3em;
    letter-spacing: 0.06em;
  }
  .dim {
    color: var(--text-3);
  }
  .accent {
    color: var(--accent);
  }
  .warn {
    color: var(--warn);
  }
  .bad {
    color: var(--bad);
  }
</style>
