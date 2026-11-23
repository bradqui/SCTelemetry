<script lang="ts">
  import { pct } from "../lib/format";

  type Tone = "auto" | "accent" | "good" | "warn" | "bad" | "muted";

  let {
    label,
    value,
    tone = "auto",
    empty = "No data",
    detail = "",
  }: { label: string; value: number | null; tone?: Tone; empty?: string; detail?: string } = $props();

  const resolved = $derived.by(() => {
    if (tone !== "auto") return tone;
    if (value == null) return "muted";
    if (value < 0.25) return "bad";
    if (value < 0.5) return "warn";
    return "good";
  });
  const width = $derived(value == null ? 0 : Math.max(0, Math.min(1, value)) * 100);
</script>

<div class="bar" class:unknown={value == null}>
  <div class="head">
    <span class="label">{label}</span>
    <span class="val num">{value == null ? empty : pct(value)}{#if detail}<small>{detail}</small>{/if}</span>
  </div>
  <div class="track {resolved}">
    <div class="fill" style:width="{width}%"></div>
  </div>
</div>

<style>
  .bar {
    display: grid;
    gap: 7px;
  }
  .head {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 8px;
  }
  .val {
    font-weight: 650;
    font-size: 1.05rem;
  }
  .val small {
    margin-left: 6px;
    font-size: 0.75rem;
    color: var(--text-3);
    font-weight: 500;
  }
  .unknown .val {
    color: var(--text-3);
    font-size: 0.85rem;
    font-weight: 500;
  }
  .track {
    height: 10px;
    border-radius: 999px;
    background: var(--bg-2);
    border: 1px solid var(--line);
    overflow: hidden;
    position: relative;
  }
  .unknown .track {
    background: repeating-linear-gradient(-45deg, var(--bg-2) 0 6px, var(--panel-2) 6px 12px);
  }
  .fill {
    height: 100%;
    border-radius: inherit;
    transition: width 0.25s linear;
  }
  .good .fill {
    background: linear-gradient(90deg, #1fae73, var(--good));
  }
  .warn .fill {
    background: linear-gradient(90deg, #c98407, var(--warn));
  }
  .bad .fill {
    background: linear-gradient(90deg, #c22c3b, var(--bad));
  }
  .accent .fill {
    background: linear-gradient(90deg, #1b8fbf, var(--accent));
  }
  .muted .fill {
    background: var(--line-2);
  }
</style>
