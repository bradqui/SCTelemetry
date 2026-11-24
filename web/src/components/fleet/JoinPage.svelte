<script lang="ts">
  import { onMount } from "svelte";
  import { api } from "../../lib/api";
  import type { HubMode } from "../../lib/types";
  import Card from "./Card.svelte";

  // /join/<code>: an invite. Players usually paste the link into their agent instead
  // (`fleet_agent link <link>`), which also sets up their PC; this page is for
  // joining from a browser, e.g. someone who only watches.
  let { mode, code }: { mode: HubMode; code: string } = $props();

  let info = $state<{ org: string; role: string } | null>(null);
  let phase = $state<"loading" | "ready" | "done" | "error">("loading");
  let error = $state("");
  let name = $state("");
  const link = location.origin + location.pathname;

  onMount(async () => {
    try {
      info = await api("GET", `/api/invite/${encodeURIComponent(code)}`);
      phase = "ready";
    } catch (e) {
      error = (e as Error).message;
      phase = "error";
    }
  });

  async function join(e: Event) {
    e.preventDefault();
    error = "";
    try {
      await api("POST", "/api/join", { code, name });
      phase = "done";
    } catch (err) {
      error = (err as Error).message;
    }
  }
</script>

<Card title={info?.org ?? mode.org} subtitle="Fleet Telemetry">
  {#if mode.me}
    <h1>You're already a member</h1>
    <p>You're signed in as <b>{mode.me.name}</b>. To link another PC, run <code>fleet_agent link {location.origin}</code> on it.</p>
    <p><a href="/">Go to the fleet</a></p>
  {:else if phase === "loading"}
    <p>Checking the invite…</p>
  {:else if phase === "error"}
    <h1>Can't use this invite</h1>
    <p class="error">{error}</p>
    <p>Ask whoever sent it for a new one.</p>
  {:else if phase === "done"}
    <h1>Welcome, {name}</h1>
    <p>
      To share your own telemetry, link your gaming PC: run <code>fleet_agent link {location.origin}</code> there and
      confirm the code it shows.
    </p>
    <p><a href="/">Go to the fleet</a></p>
  {:else if info}
    <h1>Join {info.org}{info.role === "admin" ? " as admin" : ""}</h1>
    <section>
      <h3>On your gaming PC</h3>
      <p>Paste this into the agent. It sets up your account and your PC in one go:</p>
      <p><code>fleet_agent link {link}</code></p>
    </section>
    <section>
      <h3>Or join here</h3>
      <p>For watching from this browser (you can link a PC later).</p>
      <form class="row" onsubmit={join}>
        <input bind:value={name} placeholder="Your name in the fleet" maxlength="32" required />
        <button class="btn primary">Join</button>
      </form>
    </section>
    {#if mode.discord}
      <section>
        <a class="discord" href="/auth/discord?mode=join&invite={encodeURIComponent(code)}&next=/">Join with Discord</a>
      </section>
    {/if}
    {#if error}<p class="error">{error}</p>{/if}
  {/if}
</Card>
