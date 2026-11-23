<script lang="ts">
  import type { Snippet } from "svelte";
  import { SPANS, type Span } from "../lib/panels";

  let {
    title,
    span,
    editing = false,
    pulse = null,
    bare = false,
    children,
    onSpan,
    onHide,
    onMove,
  }: {
    title: string;
    span: Span;
    editing?: boolean;
    /** Bumps when an event about this panel happens: the frame flashes. */
    pulse?: { n: number; tone: string } | null;
    /** Less padding (the heading strip). */
    bare?: boolean;
    children: Snippet;
    onSpan?: (s: Span) => void;
    onHide?: () => void;
    onMove?: (dir: -1 | 1) => void;
  } = $props();

  let el: HTMLElement;

  $effect(() => {
    if (!pulse || !el) return;
    const color = getComputedStyle(el).getPropertyValue(`--${pulse.tone === "info" ? "accent" : pulse.tone}`).trim() || "#46d3ff";
    el.animate(
      [
        { boxShadow: `0 0 0 1px ${color}, 0 0 28px ${color}66`, borderColor: color },
        { boxShadow: "0 0 0 0 transparent", borderColor: "var(--line)" },
      ],
      { duration: 1400, easing: "ease-out" },
    );
  });
</script>

<section class="frame" class:bare class:editing bind:this={el} aria-label={title}>
  <header>
    <span class="label">{title}</span>
    {#if editing}
      <div class="tools">
        <button class="tool" onclick={() => onMove?.(-1)} title="Move earlier" aria-label="Move {title} earlier">‹</button>
        <button class="tool" onclick={() => onMove?.(1)} title="Move later" aria-label="Move {title} later">›</button>
        <select
          class="tool"
          value={span}
          onchange={(e) => onSpan?.(Number(e.currentTarget.value) as Span)}
          aria-label="Width of {title}"
        >
          {#each SPANS as s (s.span)}<option value={s.span}>{s.label}</option>{/each}
        </select>
        <button class="tool" onclick={() => onHide?.()} title="Hide" aria-label="Hide {title}">✕</button>
      </div>
    {/if}
  </header>
  <div class="body">
    {@render children()}
  </div>
</section>

<style>
  .frame {
    position: relative;
    height: 100%;
    background: linear-gradient(180deg, var(--panel-2), var(--panel));
    border: 1px solid var(--line);
    border-radius: var(--radius);
    padding: 14px 18px 18px;
    min-width: 0;
    display: flex;
    flex-direction: column;
  }
  /* HUD corner brackets */
  .frame::before,
  .frame::after {
    content: "";
    position: absolute;
    width: 14px;
    height: 14px;
    border-color: color-mix(in srgb, var(--accent) 55%, transparent);
    border-style: solid;
    pointer-events: none;
    opacity: var(--brackets, 1);
  }
  .frame::before {
    top: -1px;
    left: -1px;
    border-width: 2px 0 0 2px;
    border-top-left-radius: var(--radius);
  }
  .frame::after {
    bottom: -1px;
    right: -1px;
    border-width: 0 2px 2px 0;
    border-bottom-right-radius: var(--radius);
  }
  .bare {
    padding: 10px 14px 8px;
  }
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    min-height: 22px;
    margin-bottom: 10px;
  }
  .bare header {
    margin-bottom: 2px;
  }
  header .label {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  header .label::before {
    content: "";
    width: 3px;
    height: 11px;
    border-radius: 2px;
    background: var(--accent);
    box-shadow: 0 0 6px var(--accent);
  }
  .body {
    container: panel / inline-size;
    min-width: 0;
    flex: 1;
  }
  .editing {
    border-style: dashed;
    border-color: var(--line-2);
    cursor: grab;
  }
  .editing .body {
    pointer-events: none;
    opacity: 0.75;
  }
  .tools {
    display: flex;
    gap: 4px;
  }
  .tool {
    height: 26px;
    min-width: 26px;
    border-radius: 6px;
    border: 1px solid var(--line-2);
    background: var(--bg-2);
    color: var(--text-2);
    font-size: 0.85rem;
    cursor: pointer;
    padding: 0 6px;
  }
  .tool:hover,
  .tool:focus-visible {
    color: var(--text);
    border-color: var(--accent);
    outline: none;
  }
</style>
