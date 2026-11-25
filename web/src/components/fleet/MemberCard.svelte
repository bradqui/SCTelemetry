<script lang="ts">
  import { ago, altitude, heading, LIGHT_NAMES, pct, ROLE_NAMES, speedIn, temp } from "../../lib/format";
  import type { Prefs } from "../../lib/prefs.svelte";
  import { applyTheme, DEFAULT_THEME, THEME_BY_ID, themeForShip, type Scheme, type Theme } from "../../lib/themes";
  import type { MemberSummary } from "../../lib/types";
  import { footLine } from "./roster";

  // One player at a glance: flight numbers in a ship, body numbers on foot. With
  // "match the ship" on, the card wears its ship's theme.
  let {
    m,
    prefs,
    now,
    same,
    isMe,
    onOpen,
    nameOf = () => undefined,
  }: {
    m: MemberSummary;
    prefs: Prefs;
    now: number;
    /** On your server. */
    same: boolean;
    isMe: boolean;
    onOpen: (id: string) => void;
    /** A member's display name by id (whose ship someone is aboard). */
    nameOf?: (id: string) => string | undefined;
  } = $props();

  const theme = $derived(
    (prefs.matchShip ? themeForShip(m.ship?.id) : null) ?? THEME_BY_ID[prefs.theme] ?? THEME_BY_ID[DEFAULT_THEME],
  );

  function themed(node: HTMLElement, p: { theme: Theme; scheme: Scheme }) {
    applyTheme(node, p.theme, p.scheme);
    return { update: (q: { theme: Theme; scheme: Scheme }) => applyTheme(node, q.theme, q.scheme) };
  }

  const s = $derived(m.ship);
  const v = $derived(m.vitals);
  const playing = $derived(m.presence === "live" || m.presence === "stale");
  const spd = $derived(speedIn(s?.speed, prefs.speedUnit));
  const alt = $derived(altitude(s?.alt));
  const route = $derived(m.location?.route ?? null);
  const lastArrived = $derived(m.location?.last_arrived ?? null);
  const mode = $derived.by(() => {
    if (!s) return null;
    if (s.quantum) return { text: "QT", cls: "qt" };
    if (s.powered === false) return { text: "OFF", cls: "off" };
    return s.master_mode ? { text: s.master_mode, cls: s.master_mode.toLowerCase() } : null;
  });
  const where = $derived.by(() => {
    if (m.presence === "offline") return m.last_seen ? `Offline · ${ago(m.last_seen, now)}` : "Offline";
    if (m.presence === "idle") return "Agent on · not in game";
    if (m.presence === "stale") return "Connection lost";
    if (s) return `${s.model}${m.role ? ` · ${ROLE_NAMES[m.role]}` : ""}`;
    return footLine(m, nameOf);
  });
  const ROUTE_STATE: Record<string, string> = {
    plotted: "Route set",
    en_route: "En route",
    arrived: "Arrived",
    blocked: "Obstructed",
  };
  const bars = $derived(
    v
      ? [
          { label: "Health", value: v.health, low: 0.5 },
          { label: "Oxygen", value: v.oxygen, low: 0.3 },
          { label: "Food", value: v.hunger, low: 0.25 },
          { label: "Water", value: v.thirst, low: 0.25 },
        ]
      : [],
  );
  const signed = (n: number | null | undefined) => (n == null ? "—" : `${n > 0 ? "+" : ""}${n}`);
</script>

<button
  class="card panel-frame {m.presence}"
  class:quiet={!playing}
  use:themed={{ theme, scheme: prefs.scheme }}
  onclick={() => onOpen(m.id)}
  title="Open {m.name}"
>
  <header>
    <span class="pres"></span>
    <b class="name display">{m.name}</b>
    {#if isMe}<em>you</em>{/if}
    <span class="tags">
      {#if s?.alarm}
        <span class="alarm {s.alarm}" title={s.lights.map((l) => LIGHT_NAMES[l] ?? l).join(", ")}>!</span>
      {/if}
      {#if mode}<span class="mode {mode.cls}">{mode.text}</span>{/if}
    </span>
  </header>
  <p class="where">{where}</p>

  {#if playing && s}
    {#if route && route.state !== "arrived"}
      <p class="route" class:qt={s.quantum}>
        <span>{s.quantum ? "Quantum to" : (ROUTE_STATE[route.state] ?? "Route")}</span>
        <b>{route.destination ?? "?"}</b>
      </p>
    {:else if lastArrived}
      <p class="route last" title="Where their last quantum jump ended. They may have moved on since.">
        <span>Arrived</span>
        <b>{lastArrived.destination}</b>
        <small>{ago(lastArrived.since, now)}</small>
      </p>
    {/if}
    <div class="flight">
      <div class="speed">
        {#if s.quantum}
          <!-- the game freezes the instruments mid-jump: the speed it shows means nothing -->
          <b class="display qt">QT</b>
          <small>jumping</small>
        {:else}
          <b class="display num">{spd.value}</b>
          <small>{spd.unit}</small>
        {/if}
      </div>
      <dl>
        <dt>Alt</dt>
        <dd class="num">{alt.value}<small>{alt.unit}</small></dd>
        <dt>V/S</dt>
        <dd class="num">{signed(s.vsi)}<small>m/s</small></dd>
        <dt>Hdg</dt>
        <dd class="num">{s.heading == null ? "—" : `${heading(s.heading)}°`}</dd>
        <dt>G</dt>
        <dd class="num">{s.g == null ? "—" : s.g.toFixed(1)}</dd>
      </dl>
    </div>
    {#if s.agl != null && s.agl < 5000}
      <p class="agl"><span class="label">Above ground</span> <b class="num">{Math.round(s.agl).toLocaleString()} m</b></p>
    {/if}
    <div class="meters">
      <span class="meter" class:low={s.h2_fuel != null && s.h2_fuel < 0.25}>
        <span class="label">Fuel</span>
        <i style:--v={s.h2_fuel ?? 0}></i>
        <b class="num">{pct(s.h2_fuel)}</b>
      </span>
      <span class="meter hp" class:low={v?.health != null && v.health < 0.5}>
        <span class="label">Health</span>
        <i style:--v={v?.health ?? 0}></i>
        <b class="num">{pct(v?.health)}</b>
      </span>
    </div>
    {#if s.shields.powered === false || v?.injury}
      <div class="flags">
        {#if s.shields.powered === false}<span class="flag bad">Shields down</span>{/if}
        {#if v?.injury}<span class="flag {v.injury === 'severe' ? 'bad' : 'warn'}">{v.injury} injury</span>{/if}
      </div>
    {/if}
  {:else if playing && v}
    <div class="body">
      {#each bars as b (b.label)}
        <span class="meter" class:low={b.value != null && b.value < b.low}>
          <span class="label">{b.label}</span>
          <i style:--v={b.value ?? 0}></i>
          <b class="num">{pct(b.value)}</b>
        </span>
      {/each}
    </div>
    <p class="vit">
      <span><span class="label">Body</span> <b class="num">{temp(v.body_temp)}</b></span>
      <span><span class="label">Heart</span> <b class="num">{v.heart_rate ?? "—"}</b><small>bpm</small></span>
    </p>
    {#if v.injury}
      <div class="flags">
        <span class="flag {v.injury === 'severe' ? 'bad' : 'warn'}"
          >{v.injuries > 1 ? `${v.injuries} injuries, worst ${v.injury}` : `${v.injury} injury`}</span
        >
      </div>
    {/if}
  {/if}

  {#if playing && m.location}
    <footer>
      {#if m.location.armistice}<span class="zone good">Armistice</span>{/if}
      {#if m.location.restricted}<span class="zone bad">Restricted</span>{/if}
      {#if m.location.jurisdiction}<span class="jur">{m.location.jurisdiction}</span>{/if}
      {#if same}<span class="zone srv" title="On your server">Your server</span>{/if}
    </footer>
  {/if}
</button>

<style>
  .card {
    display: grid;
    align-content: start;
    gap: 6px;
    width: 100%;
    min-width: 0;
    text-align: left;
    font: inherit;
    font-family: var(--font);
    color: var(--text);
    background: linear-gradient(180deg, var(--panel-2), var(--panel));
    border: var(--border-w) solid var(--line);
    border-radius: var(--radius);
    padding: 10px 12px 11px;
    cursor: pointer;
    position: relative;
  }
  .card:hover {
    border-color: var(--accent);
  }
  .card:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }
  .card.quiet {
    opacity: 0.72;
  }
  header {
    display: flex;
    align-items: center;
    gap: 7px;
    min-width: 0;
  }
  .pres {
    width: 8px;
    height: 8px;
    border-radius: 1px;
    background: var(--text-3);
    flex: none;
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
  .name {
    font-size: 1.05rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  em {
    font-style: normal;
    font-size: 0.56rem;
    font-weight: 800;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--accent);
    border: 1px solid currentColor;
    border-radius: var(--radius-chip);
    padding: 0 4px;
  }
  .tags {
    margin-left: auto;
    display: flex;
    gap: 4px;
    flex: none;
  }
  .mode,
  .alarm {
    display: inline-grid;
    place-items: center;
    height: 20px;
    min-width: 20px;
    padding: 0 6px;
    border-radius: var(--radius-chip);
    border: 1px solid currentColor;
    font-family: var(--mono);
    font-size: 0.66rem;
    font-weight: 800;
    letter-spacing: 0.08em;
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
    padding: 0;
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
  .where {
    margin: -3px 0 0;
    font-size: 0.78rem;
    color: var(--text-2);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .route {
    margin: 0;
    display: flex;
    gap: 6px;
    align-items: baseline;
    font-size: 0.8rem;
    padding: 3px 8px;
    border-left: 2px solid var(--nav);
    background: color-mix(in srgb, var(--nav) 8%, transparent);
    border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  }
  .route span {
    color: var(--text-3);
    font-size: 0.7rem;
  }
  .route b {
    color: var(--nav);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .route.last {
    border-left-color: var(--line-2);
    background: transparent;
  }
  .route.last b {
    color: var(--text-2);
    font-weight: 600;
  }
  .route small {
    margin-left: auto;
    color: var(--text-3);
    font-size: 0.7rem;
    white-space: nowrap;
  }
  .flight {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    gap: 10px;
    align-items: center;
  }
  .speed {
    display: grid;
    justify-items: start;
    min-width: 72px;
  }
  .speed b {
    font-size: 2rem;
    line-height: 1;
  }
  .speed b.qt {
    color: var(--nav);
  }
  .speed small {
    font-family: var(--mono);
    font-size: 0.66rem;
    color: var(--text-3);
    letter-spacing: 0.1em;
  }
  dl {
    margin: 0;
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto minmax(0, 1fr);
    gap: 3px 8px;
    align-items: baseline;
  }
  dt {
    font-size: 0.6rem;
    font-weight: 700;
    letter-spacing: var(--label-spacing);
    text-transform: var(--label-case);
    color: var(--text-3);
  }
  dd {
    margin: 0;
    font-family: var(--mono);
    font-size: 0.86rem;
    white-space: nowrap;
  }
  dd small,
  .vit small {
    font-size: 0.65em;
    color: var(--text-3);
    margin-left: 2px;
  }
  .agl {
    margin: 0;
    font-size: 0.78rem;
    display: flex;
    gap: 6px;
    align-items: baseline;
  }
  .agl b {
    font-family: var(--mono);
  }
  .meters,
  .body {
    display: grid;
    gap: 4px;
  }
  .meters {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 4px 10px;
  }
  .body {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 5px 10px;
  }
  .meter {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    align-items: center;
    gap: 6px;
    --c: var(--accent);
  }
  .meter.hp,
  .body .meter {
    --c: var(--good);
  }
  .meter.low {
    --c: var(--bad);
  }
  .meter i {
    display: block;
    height: 5px;
    border-radius: 1px;
    background: linear-gradient(90deg, var(--c) calc(var(--v) * 100%), var(--line) 0);
  }
  .meter b {
    font-family: var(--mono);
    font-size: 0.74rem;
    min-width: 34px;
    text-align: right;
  }
  .meter.low b {
    color: var(--bad);
  }
  .vit {
    margin: 0;
    display: flex;
    gap: 14px;
    font-size: 0.82rem;
  }
  .vit b {
    font-family: var(--mono);
  }
  .flags,
  footer {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    align-items: center;
  }
  .flag,
  .zone {
    font-size: 0.6rem;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    padding: 2px 6px;
    border: 1px solid currentColor;
    border-radius: var(--radius-chip);
  }
  .flag.bad,
  .zone.bad {
    color: var(--bad);
  }
  .flag.warn {
    color: var(--warn);
  }
  .zone.good {
    color: var(--good);
  }
  .zone.srv {
    color: var(--good);
    border-style: dashed;
  }
  .jur {
    font-size: 0.72rem;
    color: var(--text-2);
  }
</style>
