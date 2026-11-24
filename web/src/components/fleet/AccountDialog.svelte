<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import { api } from "../../lib/api";
  import { ago } from "../../lib/format";
  import type { Account } from "../../lib/types";
  import Dialog from "./Dialog.svelte";

  let { me, discord, onClose }: { me: Account; discord: boolean; onClose: () => void } = $props();

  interface Pc {
    id: number;
    machine: string;
    created_at: number;
    last_seen: number | null;
    connected: boolean;
  }
  let pcs = $state<Pc[] | null>(null);
  let error = $state("");
  let name = $state("");
  let saved = $state(false);
  let deviceCode = $state<{ code: string; until: number } | null>(null);
  let now = $state(Date.now());
  const hub = location.origin;

  onMount(async () => {
    name = me.name;
    try {
      pcs = await api<Pc[]>("GET", "/api/me/agents");
    } catch (e) {
      error = String((e as Error).message);
    }
  });
  const timer = setInterval(() => (now = Date.now()), 1000);
  onDestroy(() => clearInterval(timer));

  async function rename() {
    error = "";
    try {
      await api("PATCH", "/api/me", { name });
      saved = true;
      setTimeout(() => (saved = false), 1500);
    } catch (e) {
      error = (e as Error).message;
    }
  }
  async function unlink(pc: Pc) {
    if (!confirm(`Unlink ${pc.machine}? It stops sending to the fleet until you link it again.`)) return;
    try {
      await api("POST", `/api/me/agents/${pc.id}/revoke`);
      pcs = (pcs ?? []).filter((p) => p.id !== pc.id);
    } catch (e) {
      error = (e as Error).message;
    }
  }
  async function addDevice() {
    const r = await api<{ code: string; expires_in: number }>("POST", "/api/me/device-code");
    deviceCode = { code: r.code, until: Date.now() + r.expires_in * 1000 };
  }
  async function disconnectDiscord() {
    await api("POST", "/api/me/discord/disconnect");
    location.reload();
  }
  async function deleteAccount() {
    if (!confirm("Delete your account? Your PCs are unlinked and the fleet forgets your history. This can't be undone."))
      return;
    try {
      await api("DELETE", "/api/me");
      location.href = "/";
    } catch (e) {
      error = (e as Error).message;
    }
  }
  const left = $derived(deviceCode ? Math.max(0, Math.round((deviceCode.until - now) / 1000)) : 0);
</script>

<Dialog title="Your account" {onClose}>
  {#if error}<p class="error">{error}</p>{/if}

  <section>
    <h3>Display name</h3>
    <form class="row" onsubmit={(e) => (e.preventDefault(), rename())}>
      <input type="text" bind:value={name} maxlength="32" required />
      <button class="btn" type="submit">{saved ? "Saved" : "Save"}</button>
    </form>
  </section>

  <section>
    <h3>Your PCs</h3>
    <p>These send your telemetry to the fleet. To add one, run on it: <code>fleet_agent link {hub}</code></p>
    {#if pcs === null}
      <p>Loading…</p>
    {:else if pcs.length === 0}
      <p>No PCs linked yet.</p>
    {:else}
      <div class="list">
        {#each pcs as pc (pc.id)}
          <div class="item">
            <span class="dot" style:color={pc.connected ? "var(--good)" : "var(--text-3)"}></span>
            <span class="grow"
              ><b>{pc.machine}</b>
              <small
                >{pc.connected ? "Connected now" : pc.last_seen ? `Last seen ${ago(pc.last_seen, now)}` : "Never connected"}</small
              ></span
            >
            <button class="btn danger" onclick={() => unlink(pc)}>Unlink</button>
          </div>
        {/each}
      </div>
    {/if}
  </section>

  <section>
    <h3>Sign in on another device</h3>
    {#if deviceCode && left > 0}
      <p>On your phone or other PC, open <code>{hub}</code>, choose “I have a code” and enter:</p>
      <div class="secret">
        <code class="big">{deviceCode.code}</code>
        <small>{Math.floor(left / 60)}:{String(left % 60).padStart(2, "0")}</small>
      </div>
    {:else}
      <p>Get a short code to type on the other device. It works once, for 10 minutes.</p>
      <button class="btn" onclick={addDevice}>Show a code</button>
    {/if}
  </section>

  {#if discord}
    <section>
      <h3>Discord</h3>
      {#if me.discord}
        <p>Connected: you can sign in with Discord.</p>
        <button class="btn" onclick={disconnectDiscord}>Disconnect Discord</button>
      {:else}
        <p>Connect Discord to sign in with it on any device.</p>
        <a class="btn" href="/auth/discord?mode=connect&next=/">Connect Discord</a>
      {/if}
    </section>
  {/if}

  <section>
    <h3>Leave</h3>
    <p>Deleting your account unlinks your PCs and removes your history from the fleet.</p>
    <button class="btn danger" onclick={deleteAccount}>Delete my account</button>
  </section>
</Dialog>

<style>
  .big {
    font-size: 1.6rem !important;
    font-weight: 800;
    letter-spacing: 0.18em;
    color: var(--accent) !important;
  }
  a.btn {
    color: inherit;
    text-decoration: none;
    display: inline-block;
  }
</style>
