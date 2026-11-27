<script lang="ts">
  import { onMount } from "svelte";
  import { api } from "../../lib/api";
  import type { HubMode } from "../../lib/types";
  import Card from "./Card.svelte";

  // /join/<code>: an invite. Join here (with Discord, or a name), then the page walks you
  // through getting Starglance onto your PC (Welcome.svelte). The app also takes the
  // invite link itself (Settings -> Agent, or `starglance link <link>`).
  let { mode, code }: { mode: HubMode; code: string } = $props();

  let info = $state<{ org: string; role: string } | null>(null);
  let phase = $state<"loading" | "ready" | "error">("loading");
  let error = $state("");
  let name = $state("");
  let busy = $state(false);

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
    busy = true;
    try {
      await api("POST", "/api/join", { code, name });
      location.href = "/"; // signed in: the setup steps come next
    } catch (err) {
      error = (err as Error).message;
      busy = false;
    }
  }
</script>

<Card title={info?.org ?? mode.org} subtitle="Starglance" host={mode.host}>
  {#if mode.me}
    <h1>You're already a member</h1>
    <p>You're signed in as <b>{mode.me.name}</b>.</p>
    <p><a href="/">Go to the fleet</a> · <a href="/setup">Set up a PC</a></p>
  {:else if phase === "loading"}
    <p>Checking the invite…</p>
  {:else if phase === "error"}
    <h1>Can't use this invite</h1>
    <p class="error">{error}</p>
    <p>Ask whoever sent it for a new one.</p>
  {:else if info}
    <h1>Join {info.org}{info.role === "admin" ? " as admin" : ""}</h1>
    <p>See who's flying what, where, live, and share your own ship and status with the fleet.</p>
    {#if mode.discord}
      <section>
        <a class="discord" href="/auth/discord?mode=join&invite={encodeURIComponent(code)}&next=/">Join with Discord</a>
      </section>
    {/if}
    <section>
      {#if mode.discord}<h3>Or pick a name</h3>{/if}
      <form class="row" onsubmit={join}>
        <input bind:value={name} placeholder="Your name in the fleet (your in-game handle)" maxlength="32" required />
        <button class="btn primary" disabled={busy}>Join</button>
      </form>
    </section>
    <p class="next">Next, this page helps you set up Starglance on your PC: download it, then one click to link it.</p>
    {#if error}<p class="error">{error}</p>{/if}
  {/if}
</Card>

<style>
  .next {
    margin-top: 14px;
    font-size: 0.8rem;
  }
</style>
