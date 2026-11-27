<script lang="ts">
  // "Link this PC" from a hub's page: the browser handed the app a starglance:// link, the
  // agent asked the hub whose it is, and here the person says yes or no. Nothing is linked
  // before Join. Any website can open such a link, so the hub's address is shown plainly.
  import { fly } from "svelte/transition";
  import type { LinkOffer } from "../lib/types";

  let { offer }: { offer: LinkOffer } = $props();

  let telemetry = $state(true);
  let busy = $state(false);
  let error = $state("");
  let switched = $state(false);

  const host = $derived.by(() => {
    try {
      return offer.hub ? new URL(offer.hub).host : "";
    } catch {
      return offer.hub ?? "";
    }
  });

  async function answer(accept: boolean) {
    busy = true;
    error = "";
    try {
      const r = await fetch("/api/agent/offer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: offer.id, accept, telemetry: accept && telemetry && !!offer.telemetry }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(data.error ?? `The agent said ${r.status}.`);
      if (data.telemetry_changed) switched = true;
      if (accept) dispatchEvent(new CustomEvent("ft:fleets-changed"));
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = false;
    }
  }
  function close() {
    if (offer.state !== "joining") void answer(false);
  }
  function fleetSettings() {
    close();
    dispatchEvent(new CustomEvent("ft:settings", { detail: "agent" }));
  }
</script>

<div class="scrim" role="presentation" onclick={close}></div>
<div class="dialog" role="dialog" aria-modal="true" aria-label="Join a fleet" transition:fly={{ y: 12, duration: 180 }}>
  {#if offer.state === "checking"}
    <h2>Checking the link…</h2>
    <p class="hint">Asking {host || "the hub"} whose link this is.</p>
  {:else if offer.state === "error"}
    <h2>Can't use this link</h2>
    <p class="error" role="alert">{offer.error}</p>
    <div class="actions"><button class="btn" onclick={close}>Close</button></div>
  {:else if offer.state === "done"}
    <h2>You're in {offer.org ?? "the fleet"}</h2>
    <p>This PC now sends to the fleet as <b>{offer.member}</b>.</p>
    {#if switched}
      <p>The game's telemetry is switched on for {offer.telemetry?.channel}. <b>Restart Star Citizen</b> if it's running: it reads the setting when it starts.</p>
    {:else if offer.telemetry}
      <p>The game's telemetry is still off: switch it on under Settings → Agent.</p>
    {/if}
    <div class="actions">
      <button class="btn primary" onclick={close}>Done</button>
      <button class="btn" onclick={fleetSettings}>What I share…</button>
    </div>
  {:else}
    <h2>Join {offer.org ?? "this fleet"}?</h2>
    <p>
      This PC (<b>{offer.machine}</b>) will send your telemetry to the fleet at <b class="host">{host}</b>, as
      <b>{offer.member}</b>.
    </p>
    {#if offer.already && offer.already_as && offer.already_as !== offer.member}
      <p class="hint">This PC is already in this fleet as <b>{offer.already_as}</b>. Joining moves it to <b>{offer.member}</b>.</p>
    {:else if offer.already}
      <p class="hint">This PC is already in this fleet: joining again gives it a new key.</p>
    {/if}
    {#if offer.telemetry}
      <label class="check">
        <input type="checkbox" bind:checked={telemetry} />
        <span>Switch on the game's telemetry ({offer.telemetry.channel}) <small>Starglance needs it to read the game. It changes one line in the game's user.cfg; Switch off puts it back.</small></span>
      </label>
    {/if}
    <p class="hint">
      Whoever runs this hub sees what you share. Everything is shared at first; choose what under Settings → Agent. Didn't
      click Link this PC on a page you trust? Cancel.
    </p>
    {#if error}<p class="error" role="alert">{error}</p>{/if}
    <div class="actions">
      <button class="btn primary" disabled={busy || offer.state === "joining"} onclick={() => answer(true)}
        >{offer.state === "joining" ? "Joining…" : "Join"}</button
      >
      <button class="btn" disabled={offer.state === "joining"} onclick={close}>Cancel</button>
    </div>
  {/if}
</div>

<style>
  .scrim {
    position: fixed;
    inset: 0;
    z-index: 40;
    background: #0008;
  }
  .dialog {
    position: fixed;
    z-index: 41;
    left: 50%;
    top: 50%;
    transform: translate(-50%, -50%);
    width: min(460px, calc(calc(100vw / var(--z, 1)) - 24px));
    max-height: calc(calc(100vh / var(--z, 1)) - 24px);
    overflow-y: auto;
    box-sizing: border-box;
    padding: 14px 16px 16px;
    display: grid;
    gap: 10px;
    background: var(--bg);
    border: 1px solid var(--line-2);
    border-radius: var(--radius);
    box-shadow: 0 20px 60px #000a;
  }
  h2 {
    margin: 0;
    font-size: 1.15rem;
  }
  p {
    margin: 0;
    font-size: 0.88rem;
    color: var(--text-2);
  }
  .host {
    overflow-wrap: anywhere;
    color: var(--text);
  }
  .hint {
    color: var(--text-3);
    font-size: 0.8rem;
  }
  .check {
    display: flex;
    gap: 8px;
    align-items: start;
    padding: 8px 10px;
    border: 1px solid var(--line-2);
    border-radius: var(--radius-sm);
    background: var(--bg-2);
    font-size: 0.88rem;
    cursor: pointer;
  }
  .check input {
    margin-top: 3px;
  }
  .check small {
    display: block;
    color: var(--text-3);
    font-size: 0.78rem;
  }
  .actions {
    display: flex;
    gap: 6px;
  }
  .btn {
    border: 1px solid var(--line-2);
    border-radius: var(--radius-sm);
    padding: 6px 14px;
    background: var(--bg-2);
    color: var(--text);
    font: inherit;
    font-size: 0.85rem;
    cursor: pointer;
  }
  .btn:disabled {
    opacity: 0.6;
    cursor: default;
  }
  .btn.primary {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--bg);
    font-weight: 700;
  }
  .error {
    padding: 8px 10px;
    border: 1px solid var(--bad);
    border-radius: var(--radius-sm);
    color: var(--bad);
  }
</style>
