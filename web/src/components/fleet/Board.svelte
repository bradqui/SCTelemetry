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
  import Cards from "./Cards.svelte";
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
    defaultView = "overview",
    onBack,
    onHub,
    fleets = [],
    fleetHub = null,
    onPickFleet,
  }: {
    mode: HubMode;
    me: Account;
    /** Where the fleet comes from: the hub (default) or a recording (the showcase). */
    source?: FleetConnection | DemoFleet;
    /** Shared preferences (the showcase's theme switcher drives the same store). */
    store?: PrefsStore;
    /** Inside another page: fills its box, themes only itself, leaves the address alone. */
    embedded?: boolean;
    /** What the main area shows with nobody open, until the viewer picks. */
    defaultView?: "overview" | "cards";
    /** In the cockpit page: back to your own dashboard; open the hub's page. */
    onBack?: () => void;
    onHub?: () => void;
    /** The cockpit page, in several fleets: which one this is, and switching. */
    fleets?: { hub: string; label: string }[];
    fleetHub?: string | null;
    onPickFleet?: (hub: string) => void;
  } = $props();

  // Overview (totals, ships, activity) or Cards (everyone's numbers), remembered per browser.
  type View = "overview" | "cards";
  function savedView(): View {
    try {
      const v = localStorage.getItem("ft.fleet.view");
      if (v === "overview" || v === "cards") return v;
    } catch {
      /* storage unavailable */
    }
    return untrack(() => defaultView);
  }
  let view = $state<View>(savedView());
  function setView(v: View) {
    view = v;
    try {
      localStorage.setItem("ft.fleet.view", v);
    } catch {
      /* fine */
    }
  }

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

  // Back to the fleet: Esc (unless a dialog or the Customize drawer has it), or clicking
  // the open member in the roster again.
  function onKey(e: KeyboardEvent) {
    if (e.key !== "Escape" || customizing || dialog) return;
    if (fleet.focus) open(null);
    else onBack?.(); // the cockpit page: Esc on the fleet goes back to your dashboard
  }
  function toggle(id: string) {
    open(id === fleet.focus ? null : id);
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
  // Depends on the events and who's open, not on their roster row (that changes constantly).
  const memberEvents = $derived(fleet.focus ? fleet.eventsOf(fleet.focus) : []);

  async function signOut() {
    await fetch("/auth/logout", { method: "POST" });
    location.href = "/";
  }
</script>

<svelte:window onkeydown={onKey} />

<div class="board" class:embedded bind:this={root} style:--brackets={embedded ? (prefs.effects ? 1 : 0) : null}>
  <main class:detail={!!member}>
    <FleetBar
      alerts={prefs.alerts.fleet}
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
      {onBack}
      {onHub}
      {fleets}
      {fleetHub}
      {onPickFleet}
    />
    <div class="body">
      <aside>
        <Roster {rows} focus={fleet.focus} {myShard} {now} onOpen={toggle} />
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
            nameOf={(id) => fleet.roster[id]?.name}
          />
        {:else}
          <div class="views" role="tablist" aria-label="Fleet view">
            <button role="tab" aria-selected={view === "overview"} class:on={view === "overview"} onclick={() => setView("overview")}
              >Overview</button
            >
            <button role="tab" aria-selected={view === "cards"} class:on={view === "cards"} onclick={() => setView("cards")}
              >Cards</button
            >
          </div>
          {#if view === "cards"}
            <Cards {rows} meId={me.id} {myShard} {prefs} {now} onOpen={open} orderKey={fleetHub ?? location.host} />
          {:else}
            <Overview roster={fleet.roster} events={fleet.events} {now} onOpen={open} />
          {/if}
        {/if}
      </section>
    </div>
  </main>

  {#if customizing}
    <Customize {store} compact={false} selfAlerts={embedded} onClose={() => (customizing = false)} />
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
    display: grid;
    grid-template-rows: auto minmax(0, 1fr);
    align-content: start;
  }
  .main:has(> :global(.member)) {
    display: block;
  }
  .views {
    display: flex;
    gap: 2px;
    margin-bottom: var(--gap);
  }
  .views button {
    border: 1px solid var(--line-2);
    background: var(--bg-2);
    color: var(--text-3);
    border-radius: var(--radius-chip);
    padding: 3px 12px;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: var(--label-spacing);
    text-transform: var(--label-case);
    cursor: pointer;
  }
  .views button.on {
    color: var(--bg);
    background: var(--accent);
    border-color: var(--accent);
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
