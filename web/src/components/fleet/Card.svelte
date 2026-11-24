<script lang="ts">
  import type { Snippet } from "svelte";

  // A centred card for the pages before the fleet (sign in, join, link).
  let { title, subtitle, children }: { title: string; subtitle?: string; children: Snippet } = $props();
</script>

<main>
  <section class="card">
    <div class="brand">
      <svg viewBox="0 0 32 32" aria-hidden="true"><path d="M16 3 29 27H3z" /><circle cx="16" cy="20" r="3" /></svg>
      <span>{title}</span>
      {#if subtitle}<small>{subtitle}</small>{/if}
    </div>
    {@render children()}
  </section>
</main>

<style>
  main {
    min-height: 100dvh;
    display: grid;
    place-items: center;
    padding: 16px;
  }
  .card {
    width: min(440px, 100%);
    padding: 20px 22px 22px;
    border: 1px solid var(--line);
    border-radius: var(--radius);
    background: linear-gradient(180deg, var(--panel-2), var(--panel));
  }
  .brand {
    display: flex;
    align-items: center;
    gap: 9px;
    font-weight: 700;
  }
  .brand small {
    margin-left: auto;
    color: var(--text-3);
    font-weight: 600;
    font-size: 0.72rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }
  .brand svg {
    width: 22px;
    height: 22px;
    fill: none;
    stroke: var(--accent);
    stroke-width: 3;
    stroke-linejoin: round;
  }
  .brand circle {
    fill: var(--accent);
    stroke: none;
  }
  .card :global(h1) {
    font-size: 1.2rem;
    margin: 16px 0 4px;
    font-weight: 650;
  }
  .card :global(section) {
    margin-top: 14px;
  }
  .card :global(h3) {
    margin: 0 0 4px;
    font-size: 0.64rem;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--text-3);
  }
  .card :global(p) {
    color: var(--text-2);
    font-size: 0.86rem;
    margin: 0 0 8px;
  }
  .card :global(.warn) {
    color: var(--warn);
    border: 1px solid var(--warn);
    border-radius: 2px;
    padding: 6px 9px;
    margin-top: 12px;
  }
  .card :global(.error) {
    color: var(--bad);
    margin-top: 10px;
  }
  .card :global(code) {
    font-family: var(--mono);
    font-size: 0.82em;
    background: var(--bg-2);
    border: 1px solid var(--line);
    padding: 0 4px;
    border-radius: 2px;
    overflow-wrap: anywhere;
  }
  .card :global(.row) {
    display: flex;
    gap: 6px;
  }
  .card :global(input:not([type="hidden"])) {
    flex: 1;
    min-width: 0;
    padding: 7px 9px;
    border: 1px solid var(--line-2);
    border-radius: 2px;
    background: var(--bg-2);
    color: var(--text);
    font: inherit;
    font-size: 0.88rem;
  }
  .card :global(.btn) {
    border: 1px solid var(--line-2);
    background: var(--bg-2);
    border-radius: 2px;
    padding: 0 14px;
    cursor: pointer;
    font-size: 0.85rem;
    min-height: 34px;
  }
  .card :global(.btn:hover) {
    border-color: var(--accent);
  }
  .card :global(.btn.primary) {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--bg);
    font-weight: 800;
  }
  .card :global(.discord) {
    display: block;
    text-align: center;
    padding: 9px;
    border-radius: 2px;
    background: #5865f2;
    color: #fff;
    font-weight: 700;
    text-decoration: none;
  }
  .card :global(a) {
    color: var(--accent);
  }
</style>
