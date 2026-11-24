<script lang="ts">
  import type { Prefs } from "../../lib/prefs.svelte";
  import type { MemberSummary } from "../../lib/types";
  import MemberCard from "./MemberCard.svelte";

  // Everyone's basic numbers side by side, each in the same place every time you look:
  // A to Z, or your own order (drag a card to move it). Nobody moves when someone boards a
  // ship or logs off: offline people keep their place, dimmed (unless "Hide offline").
  // Saved in this browser, per fleet (orderKey).
  let {
    rows,
    meId,
    myShard,
    prefs,
    now,
    onOpen,
    orderKey = "fleet",
  }: {
    rows: MemberSummary[];
    meId: string;
    myShard: string | null;
    prefs: Prefs;
    now: number;
    onOpen: (id: string) => void;
    /** Which fleet's order (the hub): each fleet has its own. */
    orderKey?: string;
  } = $props();

  const storeKey = $derived(`ft.cards.order.${orderKey}`);
  function load(key: string): string | null {
    try {
      return localStorage.getItem(key);
    } catch {
      return null;
    }
  }
  function store(key: string, value: string | null): void {
    try {
      if (value === null) localStorage.removeItem(key);
      else localStorage.setItem(key, value);
    } catch {
      /* storage unavailable: this session only */
    }
  }

  /** Your order (member ids), or null: A to Z. */
  let custom = $state<string[] | null>(null);
  $effect(() => {
    const saved = load(storeKey);
    try {
      const ids = saved ? JSON.parse(saved) : null;
      custom = Array.isArray(ids) ? ids.filter((x) => typeof x === "string") : null;
    } catch {
      custom = null;
    }
  });
  let hideOffline = $state(load("ft.cards.hideOffline") === "1");
  $effect(() => store("ft.cards.hideOffline", hideOffline ? "1" : "0"));

  const byName = (a: MemberSummary, b: MemberSummary) =>
    a.name.localeCompare(b.name, undefined, { sensitivity: "base" }) || a.id.localeCompare(b.id);
  const ordered = $derived.by(() => {
    if (!custom) return [...rows].sort(byName);
    const pos = new Map(custom.map((id, i) => [id, i]));
    const known = rows.filter((m) => pos.has(m.id)).sort((a, b) => pos.get(a.id)! - pos.get(b.id)!);
    const fresh = rows.filter((m) => !pos.has(m.id)).sort(byName); // new to the fleet: at the end
    return [...known, ...fresh];
  });
  const shown = $derived(hideOffline ? ordered.filter((m) => m.presence !== "offline") : ordered);
  const names = $derived(new Map(rows.map((r) => [r.id, r.name])));
  const nameOf = (id: string) => names.get(id);

  // -- arranging: drag a card onto another's place

  let dragging = $state<string | null>(null);
  function dragStart(e: DragEvent, id: string) {
    dragging = id;
    e.dataTransfer?.setData("text/plain", id);
    if (e.dataTransfer) e.dataTransfer.effectAllowed = "move";
  }
  function dragOver(e: DragEvent, target: string) {
    if (!dragging) return;
    e.preventDefault();
    if (target === dragging) return;
    const ids = ordered.map((m) => m.id);
    const from = ids.indexOf(dragging);
    const to = ids.indexOf(target);
    if (from < 0 || to < 0) return;
    ids.splice(from, 1);
    ids.splice(to, 0, dragging);
    custom = ids;
  }
  function dragEnd() {
    if (dragging && custom) store(storeKey, JSON.stringify(custom));
    dragging = null;
  }
  function alphabetical() {
    custom = null;
    store(storeKey, null);
  }
</script>

<div class="cardsview">
<div class="tools">
  <span class="label">{custom ? "Your order" : "A to Z"}</span>
  <span class="hint">Drag a card to move it</span>
  {#if custom}<button class="az" onclick={alphabetical} title="Back to A to Z">A–Z</button>{/if}
  <label class="hide"><input type="checkbox" bind:checked={hideOffline} /> Hide offline</label>
</div>
<div class="cards" role="list">
  {#each shown as m (m.id)}
    <div
      class="slot"
      class:offline={m.presence === "offline"}
      class:dragging={dragging === m.id}
      role="listitem"
      draggable="true"
      ondragstart={(e) => dragStart(e, m.id)}
      ondragover={(e) => dragOver(e, m.id)}
      ondrop={(e) => e.preventDefault()}
      ondragend={dragEnd}
    >
      <MemberCard
        {m}
        {prefs}
        {now}
        isMe={m.id === meId}
        same={!!myShard && m.location?.shard === myShard && m.id !== meId}
        {onOpen}
        {nameOf}
      />
    </div>
  {:else}
    <p class="empty">{rows.length ? "Nobody's online right now." : "Nobody in this fleet yet."}</p>
  {/each}
</div>
</div>

<style>
  .cardsview {
    display: grid;
    align-content: start;
  }
  .cards {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(270px, 1fr));
    gap: var(--gap);
    align-items: stretch;
    align-content: start; /* a single row stays card-sized, not the whole height */
  }
  .empty {
    color: var(--text-3);
    margin: 0;
  }
  .tools {
    display: flex;
    align-items: center;
    gap: 10px;
    margin: -4px 0 8px;
    flex-wrap: wrap;
  }
  .tools .hint {
    color: var(--text-3);
    font-size: 0.75rem;
  }
  .az {
    border: 1px solid var(--line-2);
    background: var(--bg-2);
    color: var(--text-2);
    border-radius: var(--radius-chip);
    padding: 1px 9px;
    font-size: 0.75rem;
    font-weight: 700;
    cursor: pointer;
  }
  .hide {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 0.75rem;
    color: var(--text-3);
    cursor: pointer;
  }
  .hide input {
    accent-color: var(--accent);
  }
  .slot {
    display: grid;
    min-width: 0;
    cursor: grab;
  }
  .slot.offline {
    align-self: start; /* a short card: its place, not a whole row's height */
    opacity: 0.6;
  }
  .slot.dragging {
    opacity: 0.35;
  }
</style>
