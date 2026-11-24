<script lang="ts">
  import type { Prefs } from "../../lib/prefs.svelte";
  import type { MemberSummary } from "../../lib/types";
  import MemberCard from "./MemberCard.svelte";
  import { crewKey } from "./roster";

  // Everyone's basic numbers side by side, for flying together: ships first (crews
  // together, pilot first), then people on foot, then the rest.
  let {
    rows,
    meId,
    myShard,
    prefs,
    now,
    onOpen,
  }: {
    rows: MemberSummary[];
    meId: string;
    myShard: string | null;
    prefs: Prefs;
    now: number;
    onOpen: (id: string) => void;
  } = $props();

  const ROLE_ORDER: Record<string, number> = { pilot: 0, copilot: 1, gunner: 2, crew: 3 };
  function rank(m: MemberSummary): number {
    if (m.presence === "offline") return 4;
    if (m.presence === "idle") return 3;
    if (crewKey(m)) return 0; // in a ship, or aboard one on foot (next to its crew)
    return m.presence === "stale" ? 2 : 1;
  }
  const sorted = $derived(
    [...rows].sort(
      (a, b) =>
        rank(a) - rank(b) ||
        (crewKey(a) ?? "").localeCompare(crewKey(b) ?? "") ||
        Number(!a.ship) - Number(!b.ship) ||
        (ROLE_ORDER[a.role ?? ""] ?? 9) - (ROLE_ORDER[b.role ?? ""] ?? 9) ||
        a.name.localeCompare(b.name),
    ),
  );
  const names = $derived(new Map(rows.map((r) => [r.id, r.name])));
  const nameOf = (id: string) => names.get(id);
  const active = $derived(sorted.filter((m) => m.presence !== "offline"));
  const away = $derived(sorted.filter((m) => m.presence === "offline"));
</script>

<div class="cards">
  {#each active as m (m.id)}
    <MemberCard
      {m}
      {prefs}
      {now}
      isMe={m.id === meId}
      same={!!myShard && m.location?.shard === myShard && m.id !== meId}
      {onOpen}
      {nameOf}
    />
  {:else}
    <p class="empty">Nobody's online right now.</p>
  {/each}
</div>
{#if away.length}
  <p class="away">
    <span class="label">Offline</span>
    {#each away as m (m.id)}<button onclick={() => onOpen(m.id)}>{m.name}</button>{/each}
  </p>
{/if}

<style>
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
  .away {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    align-items: center;
    margin: 12px 0 0;
  }
  .away button {
    border: 1px solid var(--line);
    background: var(--bg-2);
    border-radius: var(--radius-chip);
    padding: 2px 9px;
    font-size: 0.78rem;
    color: var(--text-3);
    cursor: pointer;
  }
</style>
