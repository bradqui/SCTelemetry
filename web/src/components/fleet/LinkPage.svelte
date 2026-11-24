<script lang="ts">
  import { onMount } from "svelte";
  import { api } from "../../lib/api";
  import type { HubMode, Me } from "../../lib/types";
  import Card from "./Card.svelte";

  // /link?code=ABC-123: the browser half of `fleet_agent link <hub>` (another PC).
  let { mode, me }: { mode: HubMode; me: Me } = $props();

  const code = new URLSearchParams(location.search).get("code") ?? "";
  let info = $state<{ code: string; machine: string; confirmed: boolean } | null>(null);
  let phase = $state<"loading" | "ready" | "done" | "error">("loading");
  let error = $state("");

  onMount(async () => {
    if (!code) {
      phase = "error";
      error = "This page needs the code your agent showed. Run fleet_agent link again.";
      return;
    }
    try {
      info = await api("GET", `/api/link/${encodeURIComponent(code)}`);
      phase = info!.confirmed ? "done" : "ready";
    } catch (e) {
      error = (e as Error).message;
      phase = "error";
    }
  });

  async function confirm() {
    try {
      await api("POST", `/api/link/${encodeURIComponent(code)}/confirm`);
      phase = "done";
    } catch (e) {
      error = (e as Error).message;
      phase = "error";
    }
  }
</script>

<Card title={mode.org} subtitle="Link a PC">
  {#if phase === "loading"}
    <p>Checking the code…</p>
  {:else if phase === "error"}
    <h1>Can't link</h1>
    <p class="error">{error}</p>
    <p><a href="/">Go to the fleet</a></p>
  {:else if phase === "done"}
    <h1>Linked</h1>
    <p><b>{info?.machine}</b> now sends your telemetry to the fleet. The agent picks it up in a few seconds; you can close this tab.</p>
    <p><a href="/">Go to the fleet</a></p>
  {:else if info}
    <h1>Link <b>{info.machine}</b> to {me.name}?</h1>
    <p>Check this is the code your agent shows:</p>
    <div class="code">{info.code}</div>
    <p>Only confirm a code you started yourself: a linked PC sends data as you.</p>
    <div class="row">
      <button class="btn primary" onclick={confirm}>Link this PC</button>
      <a class="btn" href="/">Cancel</a>
    </div>
  {/if}
</Card>

<style>
  .code {
    font-family: var(--mono);
    font-size: 2rem;
    font-weight: 800;
    letter-spacing: 0.18em;
    text-align: center;
    padding: 10px;
    margin: 4px 0 10px;
    border: 1px solid var(--line-2);
    border-radius: var(--radius-sm);
    background: var(--bg-2);
    color: var(--accent);
  }
  a.btn {
    display: inline-grid;
    place-items: center;
    text-decoration: none;
    color: var(--text-2);
  }
</style>
