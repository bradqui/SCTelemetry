<script lang="ts">
  import { onMount, untrack } from "svelte";
  import type { DemoFleet } from "../../lib/demo-fleet.svelte";
  import { FleetConnection } from "../../lib/fleet.svelte";
  import { PrefsStore } from "../../lib/prefs.svelte";
  import { applyTheme, DEFAULT_THEME, forcedTheme, THEME_BY_ID } from "../../lib/themes";
  import Customize from "../Customize.svelte";
  import { Trends } from "../../lib/trends.svelte";
  import type { Account, HubMode } from "../../lib/types";
  import AccountDialog from "./AccountDialog.svelte";
  import AdminDialog from "./AdminDialog.svelte";
  import FleetBar from "./FleetBar.svelte";
  import MemberView from "./MemberView.svelte";
  import Overview from "./Overview.svelte";
  import Roster from "./Roster.svelte";

  let {
    mode,
    me,
    source,
    store: givenStore,
    embedded = false,
  }: {
    mode: HubMode;
    me: Account;
    /** Where the fleet comes from: the hub (default) or a recording (the showcase). */
    source?: FleetConnection | DemoFleet;
    /** Shared preferences (the showcase's theme switcher drives the same store). */
    store?: PrefsStore;
    /** Inside another page: fills its box, themes only itself, leaves the address alone. */
    embedded?: boolean;
  } = $props();

  const fleet = untrack(() => source) ?? new FleetConnection();
  const demo = untrack(() => source) !== undefined;
  const trends = new Trends();
  const store = untrack(() => givenStore) ?? new PrefsStore();
  const prefs = $derived(store.value);
  let now = $state(Date.now());
  let root: HTMLDivElement;
  // ?account or ?admin opens that dialog on load (links from docs, screenshots).
  const q = new URLSearchParams(location.search);
  let customizing = $state(!untrack(() => embedded) && q.has("customize"));
  let dialog = $state<"account" | "admin" | null>(
    untrack(() => embedded)
      ? null
      : q.has("admin") && untrack(() => me.role) === "admin"
        ? "admin"
        : q.has("account")
          ? "account"
          : null,
  );

  // The open member lives in the address (#m=<id>), so Back returns to the fleet.
  function fromHash(): string | null {
    const m = /^#m=(.+)$/.exec(location.hash);
    return m ? decodeURIComponent(m[1]) : null;
  }
  function open(id: string | null) {
    if (id === fleet.focus) return;
    if (!embedded) {
      const hash = id ? `#m=${encodeURIComponent(id)}` : " ";
      history.pushState(null, "", hash === " " ? location.pathname : hash);
    }
    fleet.open(id);
  }

  onMount(() => {
    const stop = fleet.start();
    const onPop = () => fleet.open(fromHash());
    if (!embedded) {
      fleet.open(fromHash());
      addEventListener("popstate", onPop);
    }
    const timer = setInterval(() => (now = Date.now()), 1000);
    return () => {
      stop();
      removeEventListener("popstate", onPop);
      clearInterval(timer);
    };
  });

  $effect(() => {
    fleet.focus; // a different member: start their trends afresh
    untrack(() => trends.clear());
  });
  $effect(() => {
    const snap = fleet.focusSnap;
    untrack(() => trends.push(snap));
  });
  // The fleet page wears your default theme; an open member's panel can wear their ship's.
  $effect(() => {
    const forced = forcedTheme();
    const theme = forced.theme ?? THEME_BY_ID[prefs.theme] ?? THEME_BY_ID[DEFAULT_THEME];
    if (embedded) {
      if (root) applyTheme(root, theme, forced.scheme ?? prefs.scheme);
    } else {
      applyTheme(document.documentElement, theme, forced.scheme ?? prefs.scheme);
      document.documentElement.classList.toggle("fx", prefs.effects);
    }
  });
  $effect(() => {
    JSON.stringify(store.value); // track every preference
    if (!demo) store.save();
  });
  $effect(() => {
    if (fleet.signedOut) location.reload(); // back to the sign-in page
  });

  const rows = $derived(Object.values(fleet.roster));
  const myShard = $derived(fleet.roster[me.id]?.location?.shard ?? null);
  const member = $derived(fleet.focus ? (fleet.roster[fleet.focus] ?? null) : null);
  const memberEvents = $derived(member ? fleet.eventsOf(member.id) : []);

  async function signOut() {
    await fetch("/auth/logout", { method: "POST" });
    location.href = "/";
  }
</script>

<div class="board" class:embedded bind:this={root} style:--brackets={embedded ? (prefs.effects ? 1 : 0) : null}>
  <main class:detail={!!member}>
    <FleetBar
      org={mode.org}
      {me}
      {rows}
      {demo}
      socket={fleet.socket}
      onOpen={open}
      onAccount={() => (dialog = "account")}
      onAdmin={() => (dialog = "admin")}
      onCustomize={() => (customizing = true)}
      onSignOut={signOut}
    />
    <div class="body">
      <aside>
        <Roster {rows} focus={fleet.focus} {myShard} {now} onOpen={open} />
      </aside>
      <section class="main">
        {#if member}
          <MemberView
            {member}
            snap={fleet.focusSnap}
            events={memberEvents}
            {trends}
            {prefs}
            {now}
            {myShard}
            isMe={member.id === me.id}
            onClose={() => open(null)}
          />
        {:else}
          <Overview roster={fleet.roster} events={fleet.events} {now} onOpen={open} />
        {/if}
      </section>
    </div>
  </main>

  {#if customizing}
    <Customize {store} compact={false} onClose={() => (customizing = false)} />
  {/if}

  {#if dialog === "account"}
    <AccountDialog {me} discord={mode.discord} onClose={() => (dialog = null)} />
  {:else if dialog === "admin"}
    <AdminDialog {me} onClose={() => (dialog = null)} />
  {/if}
</div>

<style>
  .board.embedded {
    height: 100%;
    background: radial-gradient(900px 500px at 70% -10%, color-mix(in srgb, var(--accent) 9%, var(--bg)) 0%, transparent 60%), var(--bg);
    color: var(--text);
    font-family: var(--font);
    color-scheme: inherit;
  }
  main {
    max-width: 2200px;
    margin: 0 auto;
    padding: 8px clamp(8px, 1vw, 14px);
    height: 100dvh;
    display: grid;
    grid-template-rows: auto minmax(0, 1fr);
    gap: var(--gap);
  }
  .embedded main {
    height: 100%;
  }
  .body {
    display: grid;
    grid-template-columns: 320px minmax(0, 1fr);
    gap: var(--gap);
    min-height: 0;
  }
  aside {
    min-height: 0;
  }
  .main {
    min-height: 0;
    overflow-y: auto;
    overflow-x: hidden;
  }
  @media (max-width: 1100px) {
    .body {
      grid-template-columns: 270px minmax(0, 1fr);
    }
  }
  /* Phones: the roster is the page; a member opens full screen. */
  @media (max-width: 760px) {
    main {
      height: auto;
      min-height: 100dvh;
    }
    .embedded main {
      min-height: 100%;
    }
    .body {
      grid-template-columns: minmax(0, 1fr);
    }
    main.detail aside,
    main:not(.detail) .main {
      display: none;
    }
    aside {
      height: calc(100dvh - 70px);
    }
    .embedded aside {
      height: 620px;
    }
  }
</style>
