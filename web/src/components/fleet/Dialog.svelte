<script lang="ts">
  import type { Snippet } from "svelte";

  let {
    title,
    wide = false,
    onClose,
    children,
  }: { title: string; wide?: boolean; onClose: () => void; children: Snippet } = $props();

  function onKey(e: KeyboardEvent) {
    if (e.key === "Escape") onClose();
  }
</script>

<svelte:window onkeydown={onKey} />

<div class="scrim" onclick={onClose} role="presentation"></div>
<div class="dialog" class:wide role="dialog" aria-modal="true" aria-label={title}>
  <header>
    <h2>{title}</h2>
    <button class="x" onclick={onClose} aria-label="Close">×</button>
  </header>
  <div class="body">{@render children()}</div>
</div>

<style>
  .scrim {
    position: fixed;
    inset: 0;
    background: #000a;
    z-index: 30;
  }
  .dialog {
    position: fixed;
    z-index: 31;
    top: 8vh;
    left: 50%;
    transform: translateX(-50%);
    width: min(520px, calc(100vw - 32px));
    max-height: 84vh;
    display: grid;
    grid-template-rows: auto minmax(0, 1fr);
    border: 1px solid var(--line-2);
    border-radius: var(--radius);
    background: var(--panel-2);
  }
  .dialog.wide {
    width: min(860px, calc(100vw - 32px));
  }
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px 8px;
    border-bottom: 1px solid var(--line);
  }
  h2 {
    margin: 0;
    font-size: 1.05rem;
  }
  .x {
    border: 0;
    background: none;
    font-size: 1.4rem;
    line-height: 1;
    cursor: pointer;
    color: var(--text-2);
  }
  .body {
    overflow-y: auto;
    padding: 12px 16px 16px;
  }
  /* Shared bits for the dialogs' content */
  .body :global(section + section) {
    margin-top: 16px;
  }
  .body :global(h3) {
    margin: 0 0 6px;
    font-size: 0.66rem;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--text-3);
  }
  .body :global(p) {
    color: var(--text-2);
    font-size: 0.85rem;
    margin: 0 0 8px;
  }
  .body :global(code) {
    font-family: var(--mono);
    font-size: 0.82em;
    background: var(--bg-2);
    border: 1px solid var(--line);
    padding: 0 4px;
    border-radius: 2px;
    overflow-wrap: anywhere;
  }
  .body :global(.btn) {
    border: 1px solid var(--line-2);
    background: var(--bg-2);
    border-radius: 2px;
    padding: 4px 10px;
    font-size: 0.8rem;
    cursor: pointer;
    white-space: nowrap;
  }
  .body :global(.btn:hover) {
    border-color: var(--accent);
  }
  .body :global(.btn.primary) {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--bg);
    font-weight: 800;
  }
  .body :global(.btn.danger:hover) {
    border-color: var(--bad);
    color: var(--bad);
  }
  .body :global(input[type="text"]),
  .body :global(select) {
    padding: 5px 8px;
    border: 1px solid var(--line-2);
    border-radius: 2px;
    background: var(--bg-2);
    color: var(--text);
    font: inherit;
    font-size: 0.85rem;
    min-width: 0;
  }
  .body :global(.row) {
    display: flex;
    gap: 6px;
    align-items: center;
    flex-wrap: wrap;
  }
  .body :global(.list) {
    display: grid;
    gap: 3px;
  }
  .body :global(.item) {
    display: flex;
    align-items: center;
    gap: 9px;
    padding: 6px 9px;
    border: 1px solid var(--line);
    border-radius: 2px;
    background: var(--bg-2);
    font-size: 0.85rem;
  }
  .body :global(.item .grow) {
    flex: 1;
    min-width: 0;
  }
  .body :global(.item small) {
    color: var(--text-3);
    font-size: 0.76rem;
  }
  .body :global(.error) {
    color: var(--bad);
    font-size: 0.82rem;
  }
  .body :global(.secret) {
    display: flex;
    gap: 6px;
    align-items: center;
    padding: 8px 10px;
    border: 1px solid var(--accent);
    border-radius: 2px;
    background: color-mix(in srgb, var(--accent) 8%, var(--bg-2));
  }
  .body :global(.secret code) {
    flex: 1;
    border: 0;
    background: none;
    font-size: 0.85rem;
    color: var(--text);
  }
</style>
