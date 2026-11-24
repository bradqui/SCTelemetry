<script lang="ts">
  import type { HubMode } from "../../lib/types";

  let { mode }: { mode: HubMode } = $props();
  const next = location.pathname + location.search + location.hash;
  const login = $derived(`${mode.login}?next=${encodeURIComponent(next)}`);
  let devName = $state("");
</script>

<main>
  <section class="card">
    <div class="brand">
      <svg viewBox="0 0 32 32" aria-hidden="true"><path d="M16 3 29 27H3z" /><circle cx="16" cy="20" r="3" /></svg>
      <span>Fleet Telemetry</span>
    </div>
    <h1>Sign in to see the fleet</h1>
    <p>Members of the org's Discord server with the member role can see everyone's status here.</p>
    {#if mode.discord}
      <a class="discord" href={login}>Sign in with Discord</a>
    {:else if !mode.dev_login}
      <p class="warn">Discord sign-in isn't set up on this hub yet.</p>
    {/if}
    {#if mode.dev_login}
      <form method="get" action="/auth/dev">
        <input type="hidden" name="next" value={next} />
        <input name="name" placeholder="Any name (test sign-in)" bind:value={devName} required maxlength="32" />
        <button type="submit">Test sign-in</button>
      </form>
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
    width: min(420px, 100%);
    padding: 22px 24px;
    border: 1px solid var(--line);
    border-radius: var(--radius);
    background: linear-gradient(180deg, var(--panel-2), var(--panel));
  }
  .brand {
    display: flex;
    align-items: center;
    gap: 9px;
    font-weight: 700;
  }
  .brand svg {
    width: 22px;
    height: 22px;
    fill: none;
    stroke: var(--accent);
    stroke-width: 3;
    stroke-linejoin: round;
  }
  .brand circle {
    fill: var(--accent);
    stroke: none;
  }
  h1 {
    font-size: 1.25rem;
    margin: 18px 0 6px;
  }
  p {
    color: var(--text-2);
    font-size: 0.9rem;
    margin: 0 0 16px;
  }
  .warn {
    color: var(--warn);
  }
  .discord {
    display: block;
    text-align: center;
    padding: 10px;
    border-radius: 2px;
    background: #5865f2;
    color: #fff;
    font-weight: 700;
    text-decoration: none;
  }
  .discord:hover {
    filter: brightness(1.1);
  }
  form {
    display: flex;
    gap: 6px;
    margin-top: 12px;
  }
  input:not([type="hidden"]) {
    flex: 1;
    min-width: 0;
    padding: 7px 9px;
    border: 1px solid var(--line-2);
    border-radius: 2px;
    background: var(--bg-2);
    color: var(--text);
    font: inherit;
    font-size: 0.88rem;
  }
  form button {
    border: 1px solid var(--line-2);
    background: var(--bg-2);
    border-radius: 2px;
    padding: 0 12px;
    cursor: pointer;
    font-size: 0.85rem;
  }
</style>
