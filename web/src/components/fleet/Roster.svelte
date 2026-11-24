<script lang="ts">
  import { ago, LIGHT_NAMES, ROLE_NAMES } from "../../lib/format";
  import type { MemberSummary } from "../../lib/types";
  import { groupRoster, type GroupBy } from "./roster";

  let {
    rows,
    focus,
    myShard,
    now,
    onOpen,
  }: {
    rows: MemberSummary[];
    focus: string | null;
    myShard: string | null;
    now: number;
    onOpen: (id: string) => void;
  } = $props();

  function initialGroup(): GroupBy {
    try {
      const g = localStorage.getItem("ft.fleet.group");
      if (g === "ship" || g === "server" || g === "status") return g;
    } catch {
      /* storage unavailable */
    }
    return "ship";
  }
  let by = $state<GroupBy>(initialGroup());
  $effect(() => {
    try {
      localStorage.setItem("ft.fleet.group", by);
    } catch {
      /* fine */
    }
  });

  const groups = $derived(groupRoster(rows, by, myShard));

  function line(m: MemberSummary): string {
    if (m.presence === "offline") return m.last_seen ? `Offline · ${ago(m.last_seen, now)}` : "Offline";
    if (m.presence === "stale") return "Connection lost";
    if (m.presence === "idle") return "Agent on · not in game";
    if (m.ship) {
      const role = m.role ? ROLE_NAMES[m.role] : null;
      return by === "ship" ? (role ?? "Aboard") : `${m.ship.model}${role ? ` · ${role}` : ""}`;
    }
    return m.locomotion === "eva" ? "EVA" : m.locomotion === "seated" ? "Seated" : "On foot";
  }

  function mode(m: MemberSummary): { text: string; cls: string; title?: string } | null {
    const s = m.ship;
    if (!s || m.presence === "offline") return null;
    if (s.quantum) {
      const dest = m.location?.route?.destination;
      return { text: "QT", cls: "qt", title: dest ? `Quantum to ${dest}` : "Quantum travel" };
    }
    if (s.powered === false) return { text: "OFF", cls: "off", title: "Powered down" };
    if (s.master_mode) return { text: s.master_mode, cls: s.master_mode.toLowerCase() };
    return null;
  }
</script>

<div class="roster">
  <div class="head">
    <span class="label">Roster</span>
    <div class="seg" role="radiogroup" aria-label="Group by">
      {#each [["ship", "Ship"], ["server", "Server"], ["status", "Status"]] as [id, text] (id)}
        <button role="radio" aria-checked={by === id} class:on={by === id} onclick={() => (by = id as GroupBy)}
          >{text}</button
        >
      {/each}
    </div>
  </div>

  <div class="list">
    {#each groups as g (g.key)}
      <section class="group" class:mine={g.mine} class:offline={g.key === "offline"}>
        <header>
          <span class="gt">{g.title}</span>
          {#if g.sub}<span class="gs">{g.sub}</span>{/if}
          <span class="gn">{g.members.length}</span>
        </header>
        {#each g.members as m (m.id)}
          {@const md = mode(m)}
          {@const same = !!myShard && m.location?.shard === myShard && m.presence !== "offline"}
          <button class="row {m.presence}" class:open={focus === m.id} onclick={() => onOpen(m.id)}>
            <span class="pres" title={m.presence}></span>
            <span class="who">
              <b>{m.name}</b>
              <small>{line(m)}</small>
            </span>
            <span class="tags">
              {#if m.location?.armistice}<span class="z good" title="Armistice zone">ARM</span>{/if}
              {#if m.location?.restricted}<span class="z bad" title="Restricted area">RES</span>{/if}
              {#if same && by !== "server"}<span class="z srv" title="On your server">SRV</span>{/if}
              {#if m.vitals?.injury}
                <span class="z {m.vitals.injury === 'severe' ? 'bad' : 'warn'}" title="{m.vitals.injury} injury"
                  >INJ</span
                >
              {/if}
              {#if m.ship?.alarm}
                <span
                  class="alarm {m.ship.alarm}"
                  title={m.ship.lights.map((l) => LIGHT_NAMES[l] ?? l).join(", ")}
                  aria-label="Warning: {m.ship.lights.join(', ')}">!</span
                >
              {/if}
              {#if md}<span class="mode {md.cls}" title={md.title}>{md.text}</span>{/if}
            </span>
            {#if m.ship && m.presence !== "offline"}
              {@const fuel = m.ship.h2_fuel}
              {@const hp = m.vitals?.health ?? null}
              <span class="meters" aria-hidden="true">
                <i class="fuel" class:low={fuel != null && fuel < 0.25} style:--v={fuel ?? 0} title="Fuel"></i>
                <i class="hp" class:low={hp != null && hp < 0.5} style:--v={hp ?? 0} title="Health"></i>
              </span>
            {/if}
          </button>
        {/each}
      </section>
    {:else}
      <p class="empty">Nobody has linked a PC yet. Members run <code>fleet_agent link</code> to join.</p>
    {/each}
  </div>
</div>

<style>
  .roster {
    display: grid;
    grid-template-rows: auto minmax(0, 1fr);
    height: 100%;
    min-height: 0;
    border: 1px solid var(--line);
    border-radius: var(--radius);
    background: linear-gradient(180deg, var(--panel-2), var(--panel));
  }
  .head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 7px 8px 7px 10px;
    border-bottom: 1px solid var(--line);
  }
  .seg {
    display: flex;
    border: 1px solid var(--line-2);
    border-radius: 2px;
    overflow: hidden;
  }
  .seg button {
    border: 0;
    background: var(--bg-2);
    color: var(--text-3);
    font-size: 0.66rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    padding: 3px 8px;
    cursor: pointer;
  }
  .seg button + button {
    border-left: 1px solid var(--line-2);
  }
  .seg button.on {
    color: var(--bg);
    background: var(--accent);
  }
  .list {
    overflow-y: auto;
    padding: 4px 0 8px;
  }
  .group header {
    display: flex;
    align-items: baseline;
    gap: 6px;
    padding: 8px 10px 3px;
    font-size: 0.64rem;
    font-weight: 800;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--text-3);
  }
  .group.mine header .gt {
    color: var(--good);
  }
  .gt {
    color: var(--text-2);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .gs {
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: none;
    font-size: 0.7rem;
    white-space: nowrap;
  }
  .gn {
    margin-left: auto;
    font-family: var(--mono);
  }
  .row {
    display: grid;
    grid-template-columns: 8px minmax(0, 1fr) auto auto;
    align-items: center;
    gap: 8px;
    width: 100%;
    padding: 5px 10px;
    border: 0;
    border-left: 2px solid transparent;
    background: none;
    text-align: left;
    cursor: pointer;
    min-height: 40px;
  }
  .row:hover {
    background: color-mix(in srgb, var(--accent) 6%, transparent);
  }
  .row.open {
    background: color-mix(in srgb, var(--accent) 11%, transparent);
    border-left-color: var(--accent);
  }
  .row:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: -2px;
  }
  .pres {
    width: 8px;
    height: 8px;
    border-radius: 1px;
    background: var(--text-3);
  }
  .live .pres {
    background: var(--good);
    box-shadow: 0 0 8px var(--good);
  }
  .idle .pres {
    background: var(--accent);
    opacity: 0.6;
  }
  .stale .pres {
    background: var(--warn);
  }
  .offline .pres {
    background: transparent;
    border: 1px solid var(--text-3);
  }
  .who {
    display: grid;
    min-width: 0;
    line-height: 1.2;
  }
  .who b,
  .who small {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .who b {
    font-size: 0.86rem;
    font-weight: 700;
  }
  .who small {
    font-size: 0.72rem;
    color: var(--text-2);
  }
  .offline .who b,
  .offline .who small {
    color: var(--text-3);
  }
  .tags {
    display: flex;
    gap: 3px;
    align-items: center;
  }
  .z,
  .mode,
  .alarm {
    display: inline-grid;
    place-items: center;
    height: 18px;
    padding: 0 4px;
    border-radius: 2px;
    border: 1px solid currentColor;
    font-size: 0.58rem;
    font-weight: 800;
    letter-spacing: 0.06em;
    line-height: 1;
  }
  .z {
    color: var(--text-3);
  }
  .z.good {
    color: var(--good);
  }
  .z.warn {
    color: var(--warn);
  }
  .z.bad {
    color: var(--bad);
  }
  .z.srv {
    color: var(--good);
    border-style: dashed;
  }
  .mode {
    font-family: var(--mono);
    min-width: 34px;
    font-size: 0.62rem;
  }
  .mode.scm {
    color: var(--scm);
    background: color-mix(in srgb, var(--scm) 12%, transparent);
  }
  .mode.nav,
  .mode.qt {
    color: var(--nav);
    background: color-mix(in srgb, var(--nav) 14%, transparent);
  }
  .mode.qt {
    animation: pulse 1.2s ease-in-out infinite;
  }
  .mode.off {
    color: var(--text-3);
  }
  .alarm {
    width: 18px;
    padding: 0;
    font-size: 0.75rem;
  }
  .alarm.minor {
    color: var(--bg);
    background: var(--warn);
    border-color: var(--warn);
  }
  .alarm.major {
    color: #fff;
    background: var(--bad);
    border-color: var(--bad);
    animation: flash 0.8s steps(1) infinite;
  }
  .meters {
    display: grid;
    gap: 3px;
    width: 30px;
  }
  .meters i {
    display: block;
    height: 3px;
    background: linear-gradient(90deg, var(--c) calc(var(--v) * 100%), var(--line) 0);
    --c: var(--good);
  }
  .meters i.fuel {
    --c: var(--accent);
  }
  .meters i.low {
    --c: var(--bad);
  }
  .empty {
    color: var(--text-3);
    font-size: 0.85rem;
    padding: 12px;
    margin: 0;
  }
  code {
    font-family: var(--mono);
    font-size: 0.85em;
  }
</style>
