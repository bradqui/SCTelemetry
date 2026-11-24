<script lang="ts">
  import { api } from "../../lib/api";
  import type { HubMode } from "../../lib/types";
  import Card from "./Card.svelte";

  let { mode }: { mode: HubMode } = $props();
  const next = location.pathname + location.search + location.hash;

  let code = $state("");
  let invite = $state("");
  let devName = $state("");
  let error = $state("");

  async function useCode(e: Event) {
    e.preventDefault();
    error = "";
    try {
      await api("POST", "/api/signin/code", { code });
      location.reload();
    } catch (err) {
      error = (err as Error).message;
    }
  }
  function useInvite(e: Event) {
    e.preventDefault();
    const m = /\/join\/([A-Za-z0-9_-]+)/.exec(invite.trim());
    const c = m ? m[1] : invite.trim();
    if (c) location.href = `/join/${encodeURIComponent(c)}`;
  }
</script>

<Card title={mode.org} subtitle="Fleet Telemetry">
  {#if mode.setup}
    <p class="warn">
      This hub has no admin yet. Its setup link is in the hub's log (for Docker: <code>docker compose logs hub</code>).
    </p>
  {/if}

  <h1>Sign in to see the fleet</h1>

  <section>
    <h3>From your gaming PC</h3>
    <p>If your agent is linked, run <code>fleet_agent open</code>, or in its cockpit view open <b>Fleet</b>, then <b>Open on the hub</b> in your name's menu.</p>
  </section>

  <section>
    <h3>I have a code</h3>
    <p>From <b>Your account → Sign in on another device</b>, on a device that's signed in.</p>
    <form class="row" onsubmit={useCode}>
      <input bind:value={code} placeholder="ABC-123" maxlength="8" autocomplete="one-time-code" required />
      <button class="btn">Sign in</button>
    </form>
  </section>

  <section>
    <h3>I have an invite</h3>
    <form class="row" onsubmit={useInvite}>
      <input bind:value={invite} placeholder="Paste the invite link" required />
      <button class="btn">Open</button>
    </form>
  </section>

  {#if mode.discord}
    <section>
      <a class="discord" href="/auth/discord?next={encodeURIComponent(next)}">Sign in with Discord</a>
    </section>
  {/if}

  {#if mode.dev_login}
    <section>
      <h3>Test sign-in (local hub only)</h3>
      <form class="row" method="get" action="/auth/dev">
        <input type="hidden" name="next" value={next} />
        <input name="name" placeholder="Any name" bind:value={devName} required maxlength="32" />
        <button class="btn" type="submit">Sign in</button>
      </form>
    </section>
  {/if}

  {#if error}<p class="error">{error}</p>{/if}
</Card>
