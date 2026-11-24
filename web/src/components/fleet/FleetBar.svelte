<script lang="ts">
  import { LIGHT_NAMES } from "../../lib/format";
  import type { Me, MemberSummary } from "../../lib/types";

  let {
    me,
    rows,
    socket,
    onOpen,
    onPcs,
    onSignOut,
  }: {
    me: Me;
    rows: MemberSummary[];
    socket: "connecting" | "open" | "closed";
    onOpen: (id: string) => void;
    onPcs: () => void;
    onSignOut: () => void;
  } = $props();

  const online = $derived(rows.filter((m) => m.presence !== "offline"));
  const inGame = $derived(rows.filter((m) => m.presence === "live" || m.presence === "stale"));
  const inShips = $derived(online.filter((m) => m.ship));

  /** Fleet-wide alarms: anyone's master warning or a bad injury. */
  const alarms = $derived.by(() => {
    const out: { id: string; name: string; text: string; level: "bad" | "warn" }[] = [];
    for (const m of online) {
      if (m.ship?.alarm === "major") {
        out.push({
          id: m.id,
          name: m.name,
          text: m.ship.lights.map((l) => LIGHT_NAMES[l] ?? l).join(", "),
          level: "bad",
        });
      } else if (m.vitals?.injury === "severe" || (m.vitals?.health != null && m.vitals.health < 0.3)) {
        out.push({ id: m.id, name: m.name, text: "Badly hurt", level: "bad" });
      } else if (m.ship?.alarm === "minor") {
        out.push({
          id: m.id,
          name: m.name,
          text: m.ship.lights.map((l) => LIGHT_NAMES[l] ?? l).join(", "),
          level: "warn",
        });
      }
    }
    return out.sort((a, b) => (a.level === b.level ? 0 : a.level === "bad" ? -1 : 1));
  });
  const worst = $derived(alarms.some((a) => a.level === "bad") ? "bad" : alarms.length ? "warn" : null);

  let menu = $state(false);
</script>

<header class="top {worst ? `alarm-${worst}` : ''}">
  <div class="brand">
    <svg viewBox="0 0 32 32" aria-hidden="true"><path d="M16 3 29 27H3z" /><circle cx="16" cy="20" r="3" /></svg>
    <span>Fleet</span>
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
          <button role="menuitem" onclick={() => ((menu = false), onPcs())}>Your PCs</button>
          <button role="menuitem" onclick={() => ((menu = false), onSignOut())}>Sign out</button>
        </div>
      {/if}
    </div>
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
    border-radius: 2px;
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
    border-radius: 2px;
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
    border-radius: 2px;
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
    color: #ffd6da;
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
    border-radius: 2px;
    padding: 3px 9px;
    font-size: 0.8rem;
    color: var(--text-2);
    cursor: pointer;
  }
  .toggle img {
    width: 18px;
    height: 18px;
    border-radius: 2px;
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
    border-radius: 2px;
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
  @media (max-width: 760px) {
    .counts .kv:nth-child(n + 2),
    .conn {
      display: none;
    }
    .alarms .who b {
      margin: 0;
    }
  }
</style>
