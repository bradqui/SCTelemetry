<script lang="ts">
  import { chosen, defaultAlerts, type Alerts } from "../../lib/alerts";
  import { LIGHT_NAMES } from "../../lib/format";
  import type { Account, MemberSummary } from "../../lib/types";
  import WindowButtons from "../WindowButtons.svelte";

  let {
    org,
    me,
    rows,
    demo = false,
    socket,
    onOpen,
    onAccount,
    onAdmin,
    onCustomize,
    onSignOut,
    onBack,
    onHub,
    fleets = [],
    fleetHub = null,
    onPickFleet,
    alerts = defaultAlerts().fleet,
  }: {
    org: string;
    me: Account;
    rows: MemberSummary[];
    /** The showcase: no account to manage. */
    demo?: boolean;
    socket: "connecting" | "open" | "closed";
    onOpen: (id: string) => void;
    onAccount: () => void;
    onAdmin: () => void;
    onCustomize: () => void;
    onSignOut: () => void;
    /** In the cockpit page: back to your own dashboard. */
    onBack?: () => void;
    /** In the cockpit page: open the hub's fleet page (phones, other screens, account). */
    onHub?: () => void;
    fleets?: { hub: string; label: string }[];
    fleetHub?: string | null;
    onPickFleet?: (hub: string) => void;
    /** Which lights the header shows (Customize → Header alerts). */
    alerts?: Alerts["fleet"];
  } = $props();

  const online = $derived(rows.filter((m) => m.presence !== "offline"));
  const inGame = $derived(rows.filter((m) => m.presence === "live" || m.presence === "stale"));
  const inShips = $derived(online.filter((m) => m.ship));

  /** Who needs attention: the lights this browser chose (by default, warnings for getting
   * hit or hostiles on radar; no cautions: thruster damage stays on for minutes), held a
   * second by the hub, and anyone badly hurt. Everything else stays on cards and dashboards. */
  const said = (lights: string[]) => lights.map((l) => LIGHT_NAMES[l] ?? l).join(", ");
  const alarms = $derived.by(() => {
    const out: { id: string; name: string; text: string; level: "bad" | "warn" }[] = [];
    for (const m of online) {
      if (!alerts.me && m.id === me.id) continue;
      // An older hub sends only the old fleet alarm: getting hit, radar; warnings.
      const lit = m.ship?.alerts ?? Object.fromEntries((m.ship?.fleet_lights ?? []).map((l) => [l, "major" as const]));
      const { warning, caution } = chosen(lit, alerts);
      const hurt = alerts.hurt && (m.vitals?.injury === "severe" || (m.vitals?.health != null && m.vitals.health < 0.3));
      if (warning.length || hurt) {
        const text = [said(warning), hurt ? "Badly hurt" : ""].filter(Boolean).join(", ");
        out.push({ id: m.id, name: m.name, text, level: "bad" });
      } else if (caution.length) {
        out.push({ id: m.id, name: m.name, text: said(caution), level: "warn" });
      }
    }
    return out.sort((a, b) => (a.level === b.level ? 0 : a.level === "bad" ? -1 : 1));
  });
  const worst = $derived(alarms.some((a) => a.level === "bad") ? "bad" : alarms.length ? "warn" : null);

  let menu = $state(false);
</script>

<header class="top topbar pywebview-drag-region {worst ? `alarm-${worst}` : ''}">
  {#if onBack}
    <button class="back" onclick={onBack} title="Back to your cockpit view">
      <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M10 3 5 8l5 5" /></svg>Cockpit
    </button>
  {/if}
  <div class="brand pywebview-drag-region">
    <svg viewBox="0 0 32 32" aria-hidden="true"><path d="M16 3 29 27H3z" /><circle cx="16" cy="20" r="3" /></svg>
    {#if fleets.length > 1 && onPickFleet}
      <select
        class="display orgpick"
        value={fleetHub}
        onchange={(e) => onPickFleet?.(e.currentTarget.value)}
        aria-label="Which fleet"
        title="Your fleets"
      >
        {#each fleets as f (f.hub)}<option value={f.hub}>{f.label}</option>{/each}
      </select>
    {:else}
      <span class="display">{org}</span>
    {/if}
  </div>

  <div class="counts" aria-label="Fleet status">
    <span class="kv"><b>Online</b><span class="num">{online.length}<small>/{rows.length}</small></span></span>
    <span class="kv"><b>In game</b><span class="num">{inGame.length}</span></span>
    <span class="kv"><b>In ships</b><span class="num">{inShips.length}</span></span>
  </div>

  {#if alarms.length}
    <div class="alarms" role="alert">
      <span class="tag {worst}">{worst === "bad" ? "Warning" : "Caution"}</span>
      {#each alarms.slice(0, 4) as a (a.id)}
        <button class="who {a.level}" onclick={() => onOpen(a.id)} title="Open {a.name}">
          <b>{a.name}</b>{a.text}
        </button>
      {/each}
      {#if alarms.length > 4}<span class="more">+{alarms.length - 4}</span>{/if}
    </div>
  {/if}

  <div class="right">
    <span class="conn" class:live={socket === "open"} title={socket === "open" ? "Connected to the hub" : "Reconnecting"}>
      <span class="dot"></span>{socket === "open" ? "Live" : "Reconnecting"}
    </span>
    <div class="me">
      <button class="toggle" onclick={() => (menu = !menu)} aria-expanded={menu}>
        {#if me.avatar}<img src={me.avatar} alt="" />{/if}{me.name}
      </button>
      {#if menu}
        <div class="menu" role="menu">
          {#if !demo}<button role="menuitem" onclick={() => ((menu = false), onAccount())}>Your account</button>{/if}
          <button role="menuitem" onclick={() => ((menu = false), onCustomize())}>Theme and layout</button>
          {#if onHub}
            <button role="menuitem" onclick={() => ((menu = false), onHub())}>Open on the hub</button>
          {/if}
          {#if me.role === "admin" && !demo}
            <button role="menuitem" onclick={() => ((menu = false), onAdmin())}>Admin</button>
          {/if}
          {#if !demo}<button role="menuitem" onclick={() => ((menu = false), onSignOut())}>Sign out</button>{/if}
        </div>
      {/if}
    </div>
    <WindowButtons />
  </div>
</header>

<style>
  .top {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 5px 12px;
    border: 1px solid var(--line);
    border-radius: var(--radius);
    background: color-mix(in srgb, var(--panel) 85%, transparent);
    min-width: 0;
    min-height: 40px;
  }
  .top.alarm-warn {
    border-color: var(--warn);
  }
  .top.alarm-bad {
    border-color: var(--bad);
    animation: alarm 1s steps(1) infinite;
  }
  @keyframes alarm {
    50% {
      background: color-mix(in srgb, var(--bad) 18%, var(--panel));
    }
  }
  .back {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    flex: none;
    border: 1px solid var(--line-2);
    background: var(--bg-2);
    color: var(--text-2);
    border-radius: var(--radius-chip);
    padding: 3px 10px 3px 6px;
    font-size: 0.78rem;
    font-weight: 600;
    cursor: pointer;
  }
  .back:hover {
    color: var(--text);
    border-color: var(--accent);
  }
  .back svg {
    width: 13px;
    height: 13px;
    fill: none;
    stroke: currentColor;
    stroke-width: 2;
  }
  .brand {
    display: flex;
    align-items: center;
    gap: 9px;
    font-weight: 700;
    flex: none;
  }
  .brand svg {
    width: 22px;
    height: 22px;
    fill: none;
    stroke: var(--accent);
    stroke-width: 3;
    stroke-linejoin: round;
  }
  .brand circle {
    fill: var(--accent);
    stroke: none;
  }
  .counts {
    display: flex;
    gap: 4px;
    flex: none;
  }
  .kv {
    display: inline-flex;
    align-items: center;
    height: 22px;
    border: 1px solid var(--line-2);
    border-radius: var(--radius-sm);
    overflow: hidden;
  }
  .kv > b,
  .kv > span {
    display: flex;
    align-items: center;
    height: 100%;
    padding: 0 7px;
  }
  .kv > b {
    font-size: 0.58rem;
    font-weight: 800;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--text-3);
    background: var(--bg-2);
    border-right: 1px solid var(--line-2);
  }
  .kv > span {
    font-weight: 800;
    font-size: 0.82rem;
  }
  .kv small {
    color: var(--text-3);
    font-weight: 600;
    font-size: 0.7rem;
    margin-left: 1px;
  }
  .alarms {
    display: flex;
    align-items: center;
    gap: 6px;
    min-width: 0;
    overflow: hidden;
    flex: 1;
  }
  .tag {
    flex: none;
    font-family: var(--mono);
    font-size: 0.68rem;
    font-weight: 800;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    padding: 2px 7px;
    border-radius: var(--radius-sm);
  }
  .tag.bad {
    background: var(--bad);
    color: #fff;
    animation: flash 0.8s steps(1) infinite;
  }
  .tag.warn {
    background: var(--warn);
    color: var(--bg);
  }
  .who {
    border: 1px solid currentColor;
    background: none;
    border-radius: var(--radius-sm);
    padding: 2px 7px;
    font-size: 0.74rem;
    cursor: pointer;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    min-width: 0;
  }
  .who b {
    margin-right: 6px;
  }
  .who.bad {
    color: color-mix(in srgb, var(--bad) 35%, var(--text));
    border-color: var(--bad);
  }
  .who.warn {
    color: var(--warn);
  }
  .more {
    color: var(--text-3);
    font-size: 0.75rem;
  }
  .right {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: 10px;
    flex: none;
  }
  .conn {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    font-size: 0.85rem;
    color: var(--warn);
  }
  .conn.live {
    color: var(--good);
  }
  .conn.live .dot {
    box-shadow: 0 0 10px var(--good);
    animation: pulse 1.6s ease-in-out infinite;
  }
  .me {
    position: relative;
  }
  .toggle {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    border: 1px solid var(--line-2);
    background: var(--bg-2);
    border-radius: var(--radius-sm);
    padding: 3px 9px;
    font-size: 0.8rem;
    color: var(--text-2);
    cursor: pointer;
  }
  .toggle img {
    width: 18px;
    height: 18px;
    border-radius: var(--radius-sm);
  }
  .toggle:hover {
    color: var(--text);
    border-color: var(--accent);
  }
  .menu {
    position: absolute;
    right: 0;
    top: calc(100% + 4px);
    z-index: 20;
    display: grid;
    min-width: 140px;
    border: 1px solid var(--line-2);
    background: var(--panel-2);
    border-radius: var(--radius-sm);
  }
  .menu button {
    border: 0;
    background: none;
    text-align: left;
    padding: 7px 12px;
    font-size: 0.82rem;
    cursor: pointer;
  }
  .menu button:hover {
    background: var(--accent-dim);
  }
  @container page (max-width: 760px) {
    .counts .kv:nth-child(n + 2),
    .conn {
      display: none;
    }
    .alarms .who b {
      margin: 0;
    }
  }
  .brand > :global(:not(select)) {
    pointer-events: none;
  }
  .orgpick {
    border: 1px solid var(--line-2);
    border-radius: var(--radius-sm);
    background: var(--bg-2);
    color: var(--text);
    font: inherit;
    font-weight: 700;
    padding: 2px 6px;
    cursor: pointer;
  }
</style>
