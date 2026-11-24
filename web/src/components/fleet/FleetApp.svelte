<script lang="ts">
  import type { HubMode } from "../../lib/types";
  import Board from "./Board.svelte";
  import LinkPage from "./LinkPage.svelte";
  import SignIn from "./SignIn.svelte";

  // The hub's page: sign in, confirm a PC link, or watch the fleet.
  let { mode }: { mode: HubMode } = $props();
  const path = location.pathname.replace(/\/+$/, "");
</script>

{#if !mode.me}
  <SignIn {mode} />
{:else if path === "/link"}
  <LinkPage me={mode.me} />
{:else}
  <Board me={mode.me} />
{/if}
