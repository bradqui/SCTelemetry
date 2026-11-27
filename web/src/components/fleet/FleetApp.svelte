<script lang="ts">
  import { untrack } from "svelte";
  import { usePageZoom } from "../../lib/pagezoom.svelte";
  import { PrefsStore } from "../../lib/prefs.svelte";
  import type { HubMode } from "../../lib/types";
  import Board from "./Board.svelte";
  import JoinPage from "./JoinPage.svelte";
  import LinkPage from "./LinkPage.svelte";
  import SignIn from "./SignIn.svelte";
  import Welcome from "./Welcome.svelte";

  // The hub's page: join with an invite, sign in, set up a PC (new members land there, and
  // /setup), confirm a PC link, or watch the fleet.
  let { mode }: { mode: HubMode } = $props();
  const path = location.pathname.replace(/\/+$/, "");
  const join = /^\/join\/([A-Za-z0-9_-]+)$/.exec(path);
  $effect(() => {
    document.title = `${mode.org} · Starglance`;
  });
  // Big screens: the same Size setting as the cockpit (Settings -> Look -> Size).
  const store = new PrefsStore();

  // New here (no PC yet): the setup steps first, until they're done or skipped.
  const SKIP = "ft.setup.skipped";
  function skipped(): boolean {
    try {
      return localStorage.getItem(SKIP) === "1";
    } catch {
      return false;
    }
  }
  // Only on a plain visit: links to somewhere (?admin, ?account, #m=...) go there.
  const plain = path === "" && !location.search && !location.hash;
  let setup = $state(
    path === "/setup" || (plain && untrack(() => mode.me !== null && mode.me.pcs === 0 && !skipped())),
  );
  function setupDone() {
    try {
      localStorage.setItem(SKIP, "1");
    } catch {
      /* fine: it just shows again */
    }
    setup = false;
    if (path === "/setup") history.replaceState(null, "", "/");
  }
  usePageZoom(() => ({ scale: store.value.scale }));
</script>

{#if join}
  <JoinPage {mode} code={join[1]} />
{:else if !mode.me}
  <SignIn {mode} />
{:else if path === "/link"}
  <LinkPage {mode} me={mode.me} />
{:else if setup}
  <Welcome {mode} me={mode.me} onDone={setupDone} />
{:else}
  <Board {mode} me={mode.me} {store} />
{/if}
