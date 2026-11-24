<script lang="ts">
  // Minimize, maximize and close for the Windows app with its title bar hidden (the top
  // bar around these is the drag area). Close hides to the tray, like the title bar's.
  import { appWindow } from "../lib/appwin.svelte";

  const show = $derived(appWindow.inApp && !!appWindow.state?.frameless);
</script>

{#if show}
  <div class="winbtns">
    <button title="Minimize" aria-label="Minimize" onclick={appWindow.minimize}>
      <svg viewBox="0 0 12 12" aria-hidden="true"><path d="M2 6.5h8" /></svg>
    </button>
    <button
      title={appWindow.state?.maximized ? "Restore" : "Maximize"}
      aria-label={appWindow.state?.maximized ? "Restore" : "Maximize"}
      onclick={() => appWindow.toggleMaximize()}
    >
      <svg viewBox="0 0 12 12" aria-hidden="true">
        {#if appWindow.state?.maximized}<path d="M3.5 4.5h5v5h-5z M5 4.5V3h4.5v4.5H8.5" />{:else}<path
            d="M2.5 2.5h7v7h-7z"
          />{/if}
      </svg>
    </button>
    <button class="close" title="Close to the tray" aria-label="Close to the tray" onclick={appWindow.hide}>
      <svg viewBox="0 0 12 12" aria-hidden="true"><path d="M3 3l6 6M9 3l-6 6" /></svg>
    </button>
  </div>
{/if}

<style>
  .winbtns {
    display: flex;
    gap: 2px;
    margin-left: 4px;
    flex: none;
  }
  button {
    width: 30px;
    height: 26px;
    display: grid;
    place-items: center;
    border: 0;
    border-radius: var(--radius-sm);
    background: none;
    color: var(--text-2);
    cursor: pointer;
  }
  button:hover {
    background: var(--bg-2);
    color: var(--text);
  }
  button.close:hover {
    background: var(--bad);
    color: #fff;
  }
  svg {
    width: 12px;
    height: 12px;
    fill: none;
    stroke: currentColor;
    stroke-width: 1.3;
  }
</style>
