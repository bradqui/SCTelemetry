<script lang="ts">
  import { onMount } from "svelte";
  import { ago } from "../../lib/format";

  let { onClose }: { onClose: () => void } = $props();

  interface Pc {
    id: number;
    machine: string;
    created_at: number;
    last_seen: number | null;
    connected: boolean;
  }
  let pcs = $state<Pc[] | null>(null);
  let error = $state<string | null>(null);

  async function load() {
    try {
      const r = await fetch("/api/me/agents");
      if (!r.ok) throw new Error(`The hub said ${r.status}`);
      pcs = await r.json();
    } catch (e) {
      error = String(e);
    }
  }
  async function revoke(pc: Pc) {
    if (!confirm(`Unlink ${pc.machine}? It stops sending to the fleet until you link it again.`)) return;
    const r = await fetch(`/api/me/agents/${pc.id}/revoke`, { method: "POST" });
    if (r.ok) pcs = (pcs ?? []).filter((p) => p.id !== pc.id);
    else error = `Couldn't unlink (${r.status}).`;
  }
  onMount(load);

  function onKey(e: KeyboardEvent) {
    if (e.key === "Escape") onClose();
  }
</script>

<svelte:window onkeydown={onKey} />

<div class="scrim" onclick={onClose} role="presentation"></div>
<div class="dialog" role="dialog" aria-modal="true" aria-labelledby="pcs-title">
  <header>
    <h2 id="pcs-title">Your PCs</h2>
    <button class="x" onclick={onClose} aria-label="Close">×</button>
  </header>
  <p class="help">
    PCs linked to your account send your telemetry to the fleet. To add one, run
    <code>fleet_agent link</code> on it.
  </p>
  {#if error}<p class="error">{error}</p>{/if}
  {#if pcs === null}
    <p class="help">Loading…</p>
  {:else if pcs.length === 0}
    <p class="help">No PCs linked yet.</p>
  {:else}
    <ul>
      {#each pcs as pc (pc.id)}
        <li>
          <span class="dot" class:on={pc.connected}></span>
          <b>{pc.machine}</b>
          <small>
            {pc.connected ? "Connected now" : pc.last_seen ? `Last seen ${ago(pc.last_seen, Date.now())}` : "Never connected"}
          </small>
          <button onclick={() => revoke(pc)}>Unlink</button>
        </li>
      {/each}
    </ul>
  {/if}
</div>

<style>
  .scrim {
    position: fixed;
    inset: 0;
    background: #0009;
    z-index: 30;
  }
  .dialog {
    position: fixed;
    z-index: 31;
    top: 12vh;
    left: 50%;
    transform: translateX(-50%);
    width: min(460px, calc(100vw - 32px));
    border: 1px solid var(--line-2);
    border-radius: var(--radius);
    background: var(--panel-2);
    padding: 14px 16px 16px;
  }
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
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
  .help {
    color: var(--text-2);
    font-size: 0.85rem;
  }
  .error {
    color: var(--bad);
    font-size: 0.85rem;
  }
  ul {
    list-style: none;
    padding: 0;
    margin: 0;
    display: grid;
    gap: 4px;
  }
  li {
    display: grid;
    grid-template-columns: 8px auto minmax(0, 1fr) auto;
    align-items: center;
    gap: 9px;
    padding: 7px 9px;
    border: 1px solid var(--line);
    border-radius: 2px;
    background: var(--bg-2);
  }
  .dot {
    color: var(--text-3);
  }
  .dot.on {
    color: var(--good);
  }
  small {
    color: var(--text-3);
    font-size: 0.76rem;
  }
  li button {
    border: 1px solid var(--line-2);
    background: none;
    border-radius: 2px;
    padding: 3px 9px;
    font-size: 0.76rem;
    cursor: pointer;
  }
  li button:hover {
    border-color: var(--bad);
    color: var(--bad);
  }
  code {
    font-family: var(--mono);
    font-size: 0.85em;
  }
</style>
