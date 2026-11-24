<script lang="ts">
  // Everyone else in your fleet, one line each, for flying together: what they're in,
  // their mode, speed and altitude. Your server first. Fed by the agent (the hub's fleet
  // stream, relayed); only connected while this panel is on screen.
  import type { PanelCtx } from "../../lib/context";
  import { altitude, ROLE_NAMES, speedIn } from "../../lib/format";
  import type { MemberSummary } from "../../lib/types";
  import { footLine } from "../fleet/roster";

  let { ctx }: { ctx: PanelCtx } = $props();

  const wing = $derived(ctx.wing ?? null);
  const meId = $derived(wing?.me?.id ?? null);
  const myShard = $derived(meId ? (wing?.roster[meId]?.location?.shard ?? null) : null);
  const names = $derived(new Map(Object.values(wing?.roster ?? {}).map((m) => [m.id, m.name])));
  const nameOf = (id: string) => names.get(id);

  const rows = $derived.by(() => {
    const all = Object.values(wing?.roster ?? {}).filter(
      (m) => m.id !== meId && (m.presence === "live" || m.presence === "stale"),
    );
    const same = (m: MemberSummary) => !!myShard && m.location?.shard === myShard;
    return all.sort(
      (a, b) =>
        Number(same(b)) - Number(same(a)) || Number(!!b.ship) - Number(!!a.ship) || a.name.localeCompare(b.name),
    );
  });
  const idle = $derived(
    Object.values(wing?.roster ?? {}).filter((m) => m.id !== meId && m.presence === "idle").length,
  );

  function what(m: MemberSummary): string {
    if (m.ship) return `${m.ship.model}${m.role ? ` · ${ROLE_NAMES[m.role]}` : ""}`;
    return footLine(m, nameOf);
  }
  function mode(m: MemberSummary): { text: string; cls: string } | null {
    const s = m.ship;
    if (!s) return null;
    if (s.quantum) return { text: "QT", cls: "qt" };
    if (s.powered === false) return { text: "OFF", cls: "off" };
    return s.master_mode ? { text: s.master_mode, cls: s.master_mode.toLowerCase() } : null;
  }
  const openFleet = () => (location.hash = "#fleet");
  const joinFleet = () => dispatchEvent(new CustomEvent("ft:settings", { detail: "agent" }));
</script>

{#if !wing || wing.unlinked}
  <p class="muted">
    Not in a fleet yet. <button class="join" onclick={joinFleet}>Join a fleet</button> with the invite link from your org's admin.
  </p>
{:else if wing.problem}
  <p class="muted">{wing.problem}</p>
{:else if !wing.me}
  <p class="muted">Connecting to the fleet…</p>
{:else if !rows.length}
  <p class="muted">Nobody else is in game{idle ? ` (${idle} with the agent on)` : ""}.</p>
{:else}
  <ul class="wing">
    {#each rows as m (m.id)}
      {@const md = mode(m)}
      {@const sp = speedIn(m.ship?.speed, ctx.prefs.speedUnit)}
      {@const alt = altitude(m.ship?.alt)}
      <li>
        <button onclick={openFleet} title="Open the fleet">
          <span class="who">
            <b class:same={!!myShard && m.location?.shard === myShard} class:stale={m.presence === "stale"}>{m.name}</b>
            <small>{what(m)}</small>
          </span>
          {#if m.ship}
            <span class="mode {md?.cls ?? 'none'}">{md?.text ?? ""}</span>
            <span class="num v">{m.ship.quantum ? "—" : sp.value}<small>{sp.unit}</small></span>
            <span class="num v">{alt.value}<small>{alt.unit}</small></span>
          {/if}
          {#if m.ship?.alarm}<span class="alarm {m.ship.alarm}" title="Warning lights">!</span>{/if}
        </button>
      </li>
    {/each}
  </ul>
{/if}

<style>
  .muted {
    margin: 0;
    color: var(--text-3);
    font-size: 0.85rem;
  }
  .join {
    display: inline;
    width: auto;
    padding: 0;
    border: 0;
    background: none;
    color: var(--accent);
    font-weight: 700;
    text-decoration: underline;
  }
  .wing {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 2px;
  }
  button {
    width: 100%;
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto 4.5em 4.5em auto;
    align-items: center;
    gap: 8px;
    padding: 3px 6px;
    border: 1px solid transparent;
    border-radius: var(--radius-sm);
    background: color-mix(in srgb, var(--bg-2) 60%, transparent);
    color: inherit;
    font: inherit;
    text-align: left;
    cursor: pointer;
  }
  button:hover {
    border-color: var(--line-2);
  }
  .who {
    display: grid;
    min-width: 0;
  }
  .who b {
    font-size: 0.86rem;
  }
  .who b.same::after {
    content: "";
    display: inline-block;
    width: 6px;
    height: 6px;
    margin-left: 6px;
    vertical-align: middle;
    border-radius: 50%;
    background: var(--good);
  }
  .who b.stale {
    color: var(--text-3);
  }
  .who small {
    color: var(--text-3);
    font-size: 0.72rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .v {
    text-align: right;
    font-size: 0.86rem;
    font-weight: 600;
  }
  .v small {
    margin-left: 2px;
    font-size: 0.65em;
    color: var(--text-3);
  }
  .mode {
    font-size: 0.66rem;
    font-weight: 800;
    padding: 1px 5px;
    border-radius: var(--radius-chip);
    border: 1px solid var(--line-2);
    color: var(--text-2);
  }
  .mode.none {
    border-color: transparent;
  }
  .mode.qt,
  .mode.nav {
    color: var(--nav);
    border-color: var(--nav);
  }
  .mode.scm {
    color: var(--accent);
    border-color: var(--accent);
  }
  .alarm {
    width: 16px;
    height: 16px;
    display: grid;
    place-items: center;
    border-radius: 50%;
    font-size: 0.7rem;
    font-weight: 800;
    color: var(--bg);
    background: var(--warn);
  }
  .alarm.major {
    background: var(--bad);
  }
  /* Columns this panel can't fit: the numbers go first. */
  @container panel (max-width: 300px) {
    button {
      grid-template-columns: minmax(0, 1fr) auto auto;
    }
    .v {
      display: none;
    }
  }
</style>
