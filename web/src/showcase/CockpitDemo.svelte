<script lang="ts">
  import { onMount } from "svelte";
  import App from "../App.svelte";
  import { DemoLive, type DemoCockpitData } from "../lib/demo-live.svelte";

  // The real cockpit view on a recorded session (demo-cockpit.json beside the page:
  // tools/demo_cockpit.py), with the replay bar. Links can start it anywhere:
  //   ?at=430         seconds into the session (default: the cruise chapter)
  //   ?at=combat      the start of a chapter (its title, any part of it)
  //   &pause          paused there (screenshots)
  //   &badge=0        without the Demo badge (screenshots)
  //   &live           as in a live session: no replay bar, "Live" in the top bar (screenshots)
  // plus the app's own: ?theme=DRAK&scheme=light, ?compact=1, ?customize.
  const q = new URLSearchParams(location.search);
  const badge = q.get("badge") !== "0";
  let live = $state.raw<DemoLive | null>(null);
  let error = $state("");
  let open = $state(true);

  function startAt(data: DemoCockpitData): number {
    // Without ?at, start in flight (the takeoff and cruise), not standing on foot.
    const at = (q.get("at") ?? "cruise").trim().toLowerCase();
    const n = Number(at);
    if (Number.isFinite(n)) return n;
    const words = at.replace(/[-_]/g, " ");
    return data.index.chapters.find((c) => c.title.toLowerCase().includes(words))?.start ?? 0;
  }

  onMount(async () => {
    try {
      const r = await fetch("./demo-cockpit.json");
      const data = (await r.json()) as DemoCockpitData;
      live = new DemoLive(data, { at: startAt(data), paused: q.has("pause"), live: q.has("live") });
      setTimeout(() => (open = false), 12_000); // then just the tag, out of the way
    } catch {
      error = "The demo recording didn't load. Reload the page to try again.";
    }
  });
</script>

{#if live}
  <App {live} demo />
{:else}
  <p class="loading">{error || "Loading the recording…"}</p>
{/if}

{#if badge && live}
  <aside class="badge" class:open>
    <button class="tag" onclick={() => (open = !open)} aria-expanded={open} title="About this demo">Demo</button>
    {#if open}
      <span class="what">A recorded flight session, played in the real cockpit view. Drag the timeline or click an event.</span>
      <a href="./">Fleet demo</a>
      <a href="../">Docs</a>
      <a href="https://github.com/bradqui/starglance/releases/latest" target="_blank" rel="noopener">Download</a>
    {/if}
  </aside>
{/if}

<style>
  .loading {
    color: var(--text-2);
    text-align: center;
    padding: 72px 16px;
    font-family: var(--font);
  }
  .badge {
    position: fixed;
    right: 12px;
    bottom: 112px;
    z-index: 30;
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px 12px;
    max-width: min(560px, calc(calc(100vw / var(--z, 1)) - 24px));
    padding: 6px 10px;
    border: 1px solid var(--line-2);
    border-radius: var(--radius-sm, 6px);
    background: var(--panel);
    box-shadow: 0 6px 24px rgb(0 0 0 / 0.35);
    font-family: var(--font);
    font-size: 0.82rem;
    color: var(--text-2);
  }
  .badge:not(.open) {
    padding: 4px;
  }
  .tag {
    font: inherit;
    font-size: 0.68rem;
    font-weight: 800;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--bg);
    background: var(--accent);
    border: 0;
    border-radius: var(--radius-chip, 4px);
    padding: 3px 8px;
    cursor: pointer;
  }
  .what {
    flex: 1 1 220px;
  }
  a {
    color: var(--accent);
    font-weight: 600;
    text-decoration: none;
  }
  a:hover {
    text-decoration: underline;
  }
</style>
