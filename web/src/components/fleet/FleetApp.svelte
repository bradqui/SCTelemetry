<script lang="ts">
  import { usePageZoom } from "../../lib/pagezoom.svelte";
  import { PrefsStore } from "../../lib/prefs.svelte";
  import type { HubMode } from "../../lib/types";
  import Board from "./Board.svelte";
  import JoinPage from "./JoinPage.svelte";
  import LinkPage from "./LinkPage.svelte";
  import SignIn from "./SignIn.svelte";

  // The hub's page: join with an invite, sign in, confirm a PC link, or watch the fleet.
  let { mode }: { mode: HubMode } = $props();
  const path = location.pathname.replace(/\/+$/, "");
  const join = /^\/join\/([A-Za-z0-9_-]+)$/.exec(path);
  $effect(() => {
    document.title = `${mode.org} · Starglance`;
  });
  // Big screens: the same Size setting as the cockpit (Settings -> Look -> Size).
  const store = new PrefsStore();
  usePageZoom(() => ({ scale: store.value.scale }));
</script>

{#if join}
  <JoinPage {mode} code={join[1]} />
{:else if !mode.me}
  <SignIn {mode} />
{:else if path === "/link"}
  <LinkPage {mode} me={mode.me} />
{:else}
  <Board {mode} me={mode.me} {store} />
{/if}
