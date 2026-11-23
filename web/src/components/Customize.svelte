<script lang="ts">
  import { fly } from "svelte/transition";
  import { COMPACT_PRESETS, PANELS, PRESETS, SPANS, type Layout, type Span } from "../lib/panels";
  import { ACCENTS, type AccentId, type PrefsStore } from "../lib/prefs.svelte";

  let { store, compact, onClose }: { store: PrefsStore; compact: boolean; onClose: () => void } = $props();

  const prefs = $derived(store.value);
  const layout = $derived<Layout>(compact ? prefs.compact : prefs.full);
  const presets = $derived(compact ? COMPACT_PRESETS : PRESETS);

  function applyPreset(l: Layout) {
    if (compact) prefs.compact = structuredClone(l);
    else prefs.full = structuredClone(l);
  }
  function move(i: number, dir: -1 | 1) {
    const j = i + dir;
    if (j < 0 || j >= layout.length) return;
    [layout[i], layout[j]] = [layout[j], layout[i]];
  }
  function onKey(e: KeyboardEvent) {
    if (e.key === "Escape") onClose();
  }
</script>

<svelte:window onkeydown={onKey} />

<aside class="drawer" transition:fly={{ x: 420, duration: 220 }} aria-label="Customize">
  <header>
    <div>
      <h2>Customize</h2>
      <p>{compact ? "Compact view" : "Full view"} · saved in this browser</p>
    </div>
    <button class="done" onclick={onClose}>Done</button>
  </header>

  <section>
    <h3>Layouts</h3>
    <div class="presets">
      {#each presets as p (p.id)}
        <button class="preset" onclick={() => applyPreset(p.layout)}>
          <b>{p.title}</b><span>{p.blurb}</span>
        </button>
      {/each}
    </div>
  </section>

  <section>
    <h3>Panels</h3>
    <p class="hint">Drag panels on the page, or use the arrows here. Sizes shrink on narrow screens.</p>
    <ul class="panels">
      {#each layout as slot, i (slot.id)}
        <li class:hidden={slot.hidden}>
          <label class="vis">
            <input
              type="checkbox"
              checked={!slot.hidden}
              onchange={(e) => (slot.hidden = !e.currentTarget.checked)}
            />
            <span>
              <b>{PANELS[slot.id].title}</b>
              <small>{PANELS[slot.id].blurb}</small>
            </span>
          </label>
          <div class="row">
            <div class="seg" role="group" aria-label="Width of {PANELS[slot.id].title}">
              {#each SPANS as s (s.span)}
                <button
                  class:on={slot.span === s.span}
                  disabled={slot.hidden}
                  onclick={() => (slot.span = s.span as Span)}
                  aria-pressed={slot.span === s.span}>{s.label}</button
                >
              {/each}
            </div>
            <button class="arrow" onclick={() => move(i, -1)} disabled={i === 0} aria-label="Move up">↑</button>
            <button class="arrow" onclick={() => move(i, 1)} disabled={i === layout.length - 1} aria-label="Move down"
              >↓</button
            >
          </div>
        </li>
      {/each}
    </ul>
  </section>

  <section>
    <h3>Look</h3>
    <div class="swatches" role="radiogroup" aria-label="Accent colour">
      {#each Object.entries(ACCENTS) as [id, a] (id)}
        <button
          class="swatch"
          class:on={prefs.accent === id}
          style:--sw={a.color}
          onclick={() => (prefs.accent = id as AccentId)}
          role="radio"
          aria-checked={prefs.accent === id}
        >
          <span></span>{a.name}
        </button>
      {/each}
    </div>
    <label class="toggle">
      <input type="checkbox" bind:checked={prefs.effects} />
      <span><b>HUD effects</b><small>Glow, scanlines and animations</small></span>
    </label>
    <label class="toggle">
      <input type="checkbox" bind:checked={prefs.caution} />
      <span><b>Master caution banner</b><small>A bar across the top while a warning light is on</small></span>
    </label>
    <label class="toggle">
      <input type="checkbox" bind:checked={prefs.autoHide} />
      <span><b>Hide ship panels on foot</b><small>Otherwise they wait on standby</small></span>
    </label>
    <div class="units">
      <span class="label">Speed in</span>
      <div class="seg">
        <button class:on={prefs.speedUnit === "ms"} onclick={() => (prefs.speedUnit = "ms")}>m/s</button>
        <button class:on={prefs.speedUnit === "kmh"} onclick={() => (prefs.speedUnit = "kmh")}>km/h</button>
      </div>
    </div>
  </section>

  <footer>
    <button class="reset" onclick={() => store.reset()}>Reset everything</button>
  </footer>
</aside>

<style>
  .drawer {
    position: fixed;
    top: 0;
    right: 0;
    bottom: 0;
    width: min(400px, 100vw);
    z-index: 30;
    overflow-y: auto;
    background: color-mix(in srgb, var(--bg) 92%, transparent);
    backdrop-filter: blur(14px);
    border-left: 1px solid var(--line-2);
    box-shadow: -20px 0 60px #0009;
    padding: 18px 18px 28px;
    display: grid;
    gap: 22px;
    align-content: start;
  }
  header {
    display: flex;
    justify-content: space-between;
    align-items: start;
    gap: 12px;
  }
  h2 {
    margin: 0;
    font-size: 1.25rem;
  }
  header p,
  .hint {
    margin: 2px 0 0;
    color: var(--text-3);
    font-size: 0.8rem;
  }
  h3 {
    margin: 0 0 10px;
    font-size: 0.72rem;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--text-3);
  }
  .hint {
    margin: -4px 0 10px;
  }
  button {
    cursor: pointer;
  }
  button:focus-visible,
  input:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }
  .done {
    border: 0;
    border-radius: 8px;
    padding: 7px 16px;
    font-weight: 700;
    background: var(--accent);
    color: var(--bg);
  }
  .presets {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }
  .preset {
    display: grid;
    gap: 2px;
    text-align: left;
    padding: 10px 12px;
    border-radius: var(--radius-sm);
    border: 1px solid var(--line-2);
    background: var(--panel);
  }
  .preset:hover {
    border-color: var(--accent);
  }
  .preset span {
    font-size: 0.75rem;
    color: var(--text-3);
  }
  .panels {
    list-style: none;
    padding: 0;
    margin: 0;
    display: grid;
    gap: 6px;
  }
  .panels li {
    display: grid;
    gap: 8px;
    padding: 10px 12px;
    border-radius: var(--radius-sm);
    border: 1px solid var(--line);
    background: var(--panel);
  }
  .panels li.hidden {
    opacity: 0.55;
  }
  .vis,
  .toggle {
    display: flex;
    gap: 10px;
    align-items: start;
    cursor: pointer;
  }
  .vis span,
  .toggle span {
    display: grid;
  }
  small {
    color: var(--text-3);
    font-size: 0.74rem;
  }
  input[type="checkbox"] {
    accent-color: var(--accent);
    width: 16px;
    height: 16px;
    margin-top: 2px;
  }
  .row {
    display: flex;
    gap: 6px;
    align-items: center;
  }
  .seg {
    display: inline-flex;
    border: 1px solid var(--line-2);
    border-radius: 8px;
    overflow: hidden;
  }
  .seg button {
    border: 0;
    background: var(--bg-2);
    padding: 4px 10px;
    font-size: 0.8rem;
    color: var(--text-2);
    border-right: 1px solid var(--line);
  }
  .seg button:last-child {
    border-right: 0;
  }
  .seg button.on {
    background: color-mix(in srgb, var(--accent) 22%, var(--bg-2));
    color: var(--text);
  }
  .seg button:disabled {
    opacity: 0.5;
    cursor: default;
  }
  .arrow {
    border: 1px solid var(--line-2);
    background: var(--bg-2);
    border-radius: 7px;
    width: 28px;
    height: 27px;
    color: var(--text-2);
  }
  .arrow:first-of-type {
    margin-left: auto;
  }
  .arrow:disabled {
    opacity: 0.35;
    cursor: default;
  }
  .swatches {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 14px;
  }
  .swatch {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 5px 11px 5px 6px;
    border-radius: 999px;
    border: 1px solid var(--line-2);
    background: var(--bg-2);
    font-size: 0.8rem;
  }
  .swatch span {
    width: 16px;
    height: 16px;
    border-radius: 50%;
    background: var(--sw);
    box-shadow: 0 0 8px var(--sw);
  }
  .swatch.on {
    border-color: var(--sw);
  }
  .toggle {
    margin-bottom: 12px;
  }
  .units {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .reset {
    border: 1px solid color-mix(in srgb, var(--bad) 45%, transparent);
    color: var(--bad);
    background: transparent;
    border-radius: 8px;
    padding: 7px 14px;
  }
</style>
