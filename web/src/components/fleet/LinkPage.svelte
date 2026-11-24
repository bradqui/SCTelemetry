<script lang="ts">
  import { onMount } from "svelte";
  import type { Me } from "../../lib/types";

  // /link?code=ABC-123: the browser half of `fleet_agent link`.
  let { me }: { me: Me } = $props();

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
    const r = await fetch(`/api/link/${encodeURIComponent(code)}`);
    const body = await r.json().catch(() => ({}));
    if (!r.ok) {
      phase = "error";
      error = body.error ?? `The hub said ${r.status}.`;
      return;
    }
    info = body;
    phase = body.confirmed ? "done" : "ready";
  });

  async function confirm() {
    const r = await fetch(`/api/link/${encodeURIComponent(code)}/confirm`, { method: "POST" });
    const body = await r.json().catch(() => ({}));
    if (r.ok) phase = "done";
    else {
      phase = "error";
      error = body.error ?? `The hub said ${r.status}.`;
    }
  }
</script>

<main>
  <section class="card">
    <span class="label">Link a PC</span>
    {#if phase === "loading"}
      <p>Checking the code…</p>
    {:else if phase === "error"}
      <h1>Can't link</h1>
      <p class="bad">{error}</p>
      <a href="/">Go to the fleet</a>
    {:else if phase === "done"}
      <h1>Linked</h1>
      <p>
        <b>{info?.machine}</b> now sends your telemetry to the fleet. The agent picks it up in a few seconds;
        you can close this tab.
      </p>
      <a href="/">Go to the fleet</a>
    {:else if info}
      <h1>Link <b>{info.machine}</b> to {me.name}?</h1>
      <p>Check this is the code your agent shows:</p>
      <div class="code">{info.code}</div>
      <p class="small">Only confirm a code you started yourself. Anyone with this PC linked sends data as you.</p>
      <div class="actions">
        <button class="primary" onclick={confirm}>Link this PC</button>
        <a href="/">Cancel</a>
      </div>
    {/if}
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
    padding: 22px 24px;
    border: 1px solid var(--line);
    border-radius: var(--radius);
    background: linear-gradient(180deg, var(--panel-2), var(--panel));
  }
  h1 {
    font-size: 1.25rem;
    margin: 10px 0 8px;
    font-weight: 650;
  }
  p {
    color: var(--text-2);
    font-size: 0.9rem;
  }
  .small {
    font-size: 0.8rem;
    color: var(--text-3);
  }
  .bad {
    color: var(--bad);
  }
  .code {
    font-family: var(--mono);
    font-size: 2rem;
    font-weight: 800;
    letter-spacing: 0.18em;
    text-align: center;
    padding: 10px;
    border: 1px solid var(--line-2);
    border-radius: 2px;
    background: var(--bg-2);
    color: var(--accent);
  }
  .actions {
    display: flex;
    align-items: center;
    gap: 14px;
  }
  .primary {
    border: 0;
    border-radius: 2px;
    padding: 9px 16px;
    background: var(--accent);
    color: var(--bg);
    font-weight: 800;
    cursor: pointer;
  }
  a {
    color: var(--accent);
    font-size: 0.88rem;
  }
</style>
