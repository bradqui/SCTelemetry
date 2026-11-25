<script lang="ts">
  // The Windows app with its title bar hidden has no border to grab: thin edges and
  // corners around the page that hand a press to Windows' own resizing (app.py
  // start_resize). Not when maximized, and never in a browser.
  import { appWindow } from "../lib/appwin.svelte";

  const show = $derived(appWindow.inApp && !!appWindow.state?.frameless && !appWindow.state?.maximized);
  const EDGES = ["top", "bottom", "left", "right", "top-left", "top-right", "bottom-left", "bottom-right"];

  function press(e: PointerEvent, edge: string) {
    if (e.button !== 0) return;
    e.preventDefault();
    appWindow.startResize(edge);
  }
</script>

{#if show}
  {#each EDGES as edge (edge)}
    <div class="edge {edge}" aria-hidden="true" onpointerdown={(e) => press(e, edge)}></div>
  {/each}
{/if}

<style>
  .edge {
    position: fixed;
    z-index: 1000;
    --t: 5px;
    --c: 10px;
  }
  .top,
  .bottom {
    left: var(--c);
    right: var(--c);
    height: var(--t);
    cursor: ns-resize;
  }
  .top {
    top: 0;
  }
  .bottom {
    bottom: 0;
  }
  .left,
  .right {
    top: var(--c);
    bottom: var(--c);
    width: var(--t);
    cursor: ew-resize;
  }
  .left {
    left: 0;
  }
  .right {
    right: 0;
  }
  .top-left,
  .top-right,
  .bottom-left,
  .bottom-right {
    width: var(--c);
    height: var(--c);
  }
  .top-left {
    top: 0;
    left: 0;
    cursor: nwse-resize;
  }
  .bottom-right {
    bottom: 0;
    right: 0;
    cursor: nwse-resize;
  }
  .top-right {
    top: 0;
    right: 0;
    cursor: nesw-resize;
  }
  .bottom-left {
    bottom: 0;
    left: 0;
    cursor: nesw-resize;
  }
</style>
