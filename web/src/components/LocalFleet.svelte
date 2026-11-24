<script lang="ts">
  // The fleet in the cockpit page: the hub's fleet board, fed by this PC's agent (it signs
  // in to the hub with the PC's link and relays the stream). Same board as the hub's page.
  import { onMount } from "svelte";
  import { FleetConnection } from "../lib/fleet.svelte";
  import { openOnHub } from "../lib/hub";
  import type { PrefsStore } from "../lib/prefs.svelte";
  import type { Account, HubMode } from "../lib/types";
  import Board from "./fleet/Board.svelte";

  let { store, onBack }: { store: PrefsStore; onBack: () => void } = $props();

  const fleet = new FleetConnection({ local: true });
  onMount(() => fleet.start());

  const me = $derived<Account | null>(
    fleet.me ? { ...fleet.me, role: "member", active: true, discord: false, created_at: 0 } : null,
  );
  const mode = $derived<HubMode>({
    mode: "fleet",
    hub_version: "",
    org: fleet.org ?? "Fleet",
    me,
    discord: false,
    dev_login: false,
    setup: false,
  });
</script>

<div class="local-fleet">
  {#if me}
    <Board {mode} {me} source={fleet} {store} embedded defaultView="cards" {onBack} onHub={openOnHub} />
  {:else}
    <section class="waiting">
      <button class="back" onclick={onBack}>‹ Cockpit</button>
      {#if fleet.unlinked}
        <h1>Not in a fleet yet</h1>
        <p>Paste the invite link from your org's admin in the agent's settings.</p>
        <button class="join" onclick={() => dispatchEvent(new CustomEvent("ft:settings", { detail: "agent" }))}
          >Join a fleet</button
        >
      {:else if fleet.problem}
        <h1>Can't show the fleet</h1>
        <p>{fleet.problem} Trying again…</p>
      {:else if fleet.socket === "closed"}
        <h1>Can't reach the agent</h1>
        <p>Start it with <code>python -m fleet_agent run</code>. This page reconnects by itself.</p>
      {:else}
        <h1>Connecting to the fleet…</h1>
      {/if}
    </section>
  {/if}
</div>

<style>
  .local-fleet {
    height: 100dvh;
  }
  .waiting {
    max-width: 560px;
    margin: 12vh auto 0;
    padding: 0 16px;
    text-align: center;
    color: var(--text-2);
  }
  .waiting h1 {
    font-size: 1.3rem;
    color: var(--text);
  }
  .back {
    border: 1px solid var(--line-2);
    background: var(--bg-2);
    color: var(--text-2);
    border-radius: var(--radius-chip);
    padding: 3px 10px;
    cursor: pointer;
  }
  code {
    font-family: var(--mono);
    font-size: 0.85em;
  }
  .join {
    border: 0;
    border-radius: var(--radius-sm);
    padding: 7px 16px;
    font-weight: 700;
    background: var(--accent);
    color: var(--bg);
    cursor: pointer;
  }
</style>
