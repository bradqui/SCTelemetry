<script lang="ts">
  import { onMount, untrack } from "svelte";
  import { FleetConnection } from "../../lib/fleet.svelte";
  import { ACCENTS, PrefsStore } from "../../lib/prefs.svelte";
  import { Trends } from "../../lib/trends.svelte";
  import type { Account, HubMode } from "../../lib/types";
  import AccountDialog from "./AccountDialog.svelte";
  import AdminDialog from "./AdminDialog.svelte";
  import FleetBar from "./FleetBar.svelte";
  import MemberView from "./MemberView.svelte";
  import Overview from "./Overview.svelte";
  import Roster from "./Roster.svelte";

  let { mode, me }: { mode: HubMode; me: Account } = $props();

  const fleet = new FleetConnection();
  const trends = new Trends();
  const store = new PrefsStore();
  const prefs = $derived(store.value);
  let now = $state(Date.now());
  // ?account or ?admin opens that dialog on load (links from docs, screenshots).
  const q = new URLSearchParams(location.search);
  let dialog = $state<"account" | "admin" | null>(
    q.has("admin") && untrack(() => me.role) === "admin" ? "admin" : q.has("account") ? "account" : null,
  );

  // The open member lives in the address (#m=<id>), so Back returns to the fleet.
  function fromHash(): string | null {
    const m = /^#m=(.+)$/.exec(location.hash);
    return m ? decodeURIComponent(m[1]) : null;
  }
  function open(id: string | null) {
    if (id === fleet.focus) return;
    const hash = id ? `#m=${encodeURIComponent(id)}` : " ";
    history.pushState(null, "", hash === " " ? location.pathname : hash);
    fleet.open(id);
  }

  onMount(() => {
    const stop = fleet.start();
    fleet.open(fromHash());
    const onPop = () => fleet.open(fromHash());
    addEventListener("popstate", onPop);
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
  $effect(() => {
    const color = ACCENTS[prefs.accent].color;
    document.documentElement.style.setProperty("--accent", color);
    document.documentElement.style.setProperty("--accent-dim", `${color}33`);
    document.documentElement.classList.toggle("fx", prefs.effects);
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

<main class:detail={!!member}>
  <FleetBar
    org={mode.org}
    {me}
    {rows}
    socket={fleet.socket}
    onOpen={open}
    onAccount={() => (dialog = "account")}
    onAdmin={() => (dialog = "admin")}
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

{#if dialog === "account"}
  <AccountDialog {me} discord={mode.discord} onClose={() => (dialog = null)} />
{:else if dialog === "admin"}
  <AdminDialog {me} onClose={() => (dialog = null)} />
{/if}

<style>
  main {
    max-width: 2200px;
    margin: 0 auto;
    padding: 8px clamp(8px, 1vw, 14px);
    height: 100dvh;
    display: grid;
    grid-template-rows: auto minmax(0, 1fr);
    gap: var(--gap);
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
  }
</style>
