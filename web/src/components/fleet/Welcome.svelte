<script lang="ts">
  // Where a new member lands (joined with an invite or with Discord, no PC linked yet), and
  // /setup for adding a PC later: get Starglance onto this PC and link it, or skip to watch.
  import { untrack } from "svelte";
  import type { Account, HubMode } from "../../lib/types";
  import Card from "./Card.svelte";
  import SetupPC from "./SetupPC.svelte";

  let { mode, me, onDone }: { mode: HubMode; me: Account; onDone: () => void } = $props();
  let linked = $state(false);
  const first = untrack(() => (me.pcs ?? 0) === 0); // as it was on arrival
</script>

<Card title={mode.org} subtitle="Starglance" host={mode.host}>
  <h1>{first ? `Welcome aboard, ${me.name}` : "Set up Starglance on this PC"}</h1>
  <p>
    {linked
      ? "All set. Start Star Citizen and you'll show up in the fleet."
      : first
      ? "You're in the fleet. Set up Starglance on the PC you play on, and the fleet sees your ship, crew and status live, and you see theirs."
      : "Link the PC you play on, and it sends to the fleet whenever Starglance is running."}
  </p>
  <section>
    <SetupPC {mode} onLinked={() => (linked = true)} />
  </section>
  <section class="end">
    {#if linked}
      <button class="btn primary" onclick={onDone}>Go to the fleet</button>
    {:else}
      <button class="skip" onclick={onDone}>{first ? "Skip for now: just watch the fleet" : "Back to the fleet"}</button>
    {/if}
  </section>
</Card>

<style>
  .end {
    display: flex;
    justify-content: flex-end;
  }
  .skip {
    border: 0;
    background: none;
    padding: 4px 0;
    color: var(--text-3);
    font: inherit;
    font-size: 0.82rem;
    cursor: pointer;
  }
  @media (hover: hover) {
    .skip:hover {
      color: var(--accent);
    }
  }
</style>
