<script lang="ts">
  import { fly } from "svelte/transition";
  import { COMPACT_PRESETS, PANELS, PRESETS, SPANS, type Layout, type Span } from "../lib/panels";
  import type { PrefsStore } from "../lib/prefs.svelte";
  import { palette, THEMES } from "../lib/themes";
  import type { Destroyed } from "../lib/format";
  import type { Focus } from "../lib/phase";
  import type { UpdaterStatus, UplinkStatus } from "../lib/types";
  import { awake, wakeSupport } from "../lib/wakelock.svelte";
  import AgentSettings from "./AgentSettings.svelte";
  import HeaderAlerts from "./HeaderAlerts.svelte";

  let {
    store,
    compact,
    onClose,
    agent = false,
    uplinks = {},
    updater = null,
    tab: startTab = "dashboard",
    selfAlerts = true,
  }: {
    store: PrefsStore;
    compact: boolean;
    onClose: () => void;
    /** The cockpit page: also the Agent tab (this PC's fleet link, sharing, telemetry). */
    agent?: boolean;
    uplinks?: Record<string, UplinkStatus>;
    updater?: UpdaterStatus | null;
    tab?: "dashboard" | "agent";
    /** Header alerts: your top bar's columns too (the cockpit view, not the hub's page). */
    selfAlerts?: boolean;
  } = $props();
  let tab = $state<"dashboard" | "agent">("dashboard");
  $effect.pre(() => {
    tab = agent ? startTab : "dashboard";
  });

  const prefs = $derived(store.value);
  const wake = wakeSupport();
  const FOCUS: { id: Focus; label: string }[] = [
    { id: "off", label: "Off" },
    { id: "spot", label: "Spotlight" },
    { id: "strip", label: "Focus strip" },
    { id: "both", label: "Both" },
  ];
  const DESTROYED: { id: Destroyed; label: string }[] = [
    { id: "none", label: "None" },
    { id: "fleet", label: "Fleet" },
    { id: "players", label: "Players" },
    { id: "all", label: "All" },
  ];
  const layout = $derived<Layout>(compact ? prefs.compact : prefs.full);
  const presets = $derived(compact ? COMPACT_PRESETS : PRESETS);

  function applyPreset(l: Layout) {
    if (compact) prefs.compact = structuredClone(l);
    else prefs.full = structuredClone(l);
  }
  function move(i: number, dir: -1 | 1) {
    const j = i + dir;
    if (j < 0 || j >= layout.length) return;
    [layout[i], layout[j]] = [layout[j], layout[i]];
  }
  function onKey(e: KeyboardEvent) {
    if (e.key === "Escape") onClose();
  }
</script>

<svelte:window onkeydown={onKey} />

<aside class="drawer" transition:fly={{ x: 420, duration: 220 }} aria-label="Settings">
  <header>
    <div>
      <h2>{agent ? "Settings" : "Customize"}</h2>
      <p>
        {tab === "agent" ? "This PC's agent · saved by the agent" : `${compact ? "Compact" : "Full"} view · saved in this browser`}
      </p>
    </div>
    <button class="done" onclick={onClose}>Done</button>
  </header>

  {#if agent}
    <div class="tabs" role="tablist">
      <button role="tab" aria-selected={tab === "dashboard"} class:on={tab === "dashboard"} onclick={() => (tab = "dashboard")}
        >Dashboard</button
      >
      <button role="tab" aria-selected={tab === "agent"} class:on={tab === "agent"} onclick={() => (tab = "agent")}>Agent</button>
    </div>
  {/if}

  {#if tab === "agent"}
    <AgentSettings {uplinks} {updater} />
  {:else}

  <section>
    <h3>Theme</h3>
    <div class="units">
      <span class="label">Scheme</span>
      <div class="seg">
        <button class:on={prefs.scheme === "dark"} onclick={() => (prefs.scheme = "dark")} aria-pressed={prefs.scheme === "dark"}
          >Dark</button
        >
        <button class:on={prefs.scheme === "light"} onclick={() => (prefs.scheme = "light")} aria-pressed={prefs.scheme === "light"}
          >Light</button
        >
      </div>
    </div>
    <label class="toggle">
      <input type="checkbox" bind:checked={prefs.matchShip} />
      <span><b>Match the ship I'm in</b><small>Take on the maker of whatever you board; back to your default when you get out</small></span>
    </label>
    <span class="label">{prefs.matchShip ? "On foot, use" : "Theme"}</span>
    <div class="themes" role="radiogroup" aria-label="Default theme">
      {#each THEMES as t (t.id)}
        {@const p = palette(t, prefs.scheme)}
        <button
          class="theme"
          class:on={prefs.theme === t.id}
          onclick={() => (prefs.theme = t.id)}
          role="radio"
          aria-checked={prefs.theme === t.id}
          title={t.name}
        >
          <span class="sw" style:background="linear-gradient(135deg, {p.panel} 0 50%, {p.accent} 50%)"></span>
          <b>{t.short}</b>
          <small>{t.tagline}</small>
        </button>
      {/each}
    </div>
  </section>

  <section>
    <h3>Layouts</h3>
    <div class="presets">
      {#each presets as p (p.id)}
        <button class="preset" onclick={() => applyPreset(p.layout)}>
          <b>{p.title}</b><span>{p.blurb}</span>
        </button>
      {/each}
    </div>
  </section>

  <section>
    <h3>Panels</h3>
    <p class="hint">Drag panels on the page, or use the arrows here. Sizes shrink on narrow screens.</p>
    <ul class="panels">
      {#each layout as slot, i (slot.id)}
        <li class:hidden={slot.hidden}>
          <label class="vis">
            <input
              type="checkbox"
              checked={!slot.hidden}
              onchange={(e) => (slot.hidden = !e.currentTarget.checked)}
            />
            <span>
              <b>{PANELS[slot.id].title}</b>
              <small>{PANELS[slot.id].blurb}</small>
            </span>
          </label>
          <div class="row">
            <div class="seg" role="group" aria-label="Width of {PANELS[slot.id].title}">
              {#each SPANS as s (s.span)}
                <button
                  class:on={slot.span === s.span}
                  disabled={slot.hidden}
                  onclick={() => (slot.span = s.span as Span)}
                  aria-pressed={slot.span === s.span}>{s.label}</button
                >
              {/each}
            </div>
            <button class="arrow" onclick={() => move(i, -1)} disabled={i === 0} aria-label="Move up">↑</button>
            <button class="arrow" onclick={() => move(i, 1)} disabled={i === layout.length - 1} aria-label="Move down"
              >↓</button
            >
          </div>
        </li>
      {/each}
    </ul>
  </section>

  <section>
    <h3>Flight phases</h3>
    <div class="units">
      <span class="label">Follow the flight</span>
      <div class="seg" role="group" aria-label="Follow the flight">
        {#each FOCUS as f (f.id)}
          <button class:on={prefs.focus === f.id} onclick={() => (prefs.focus = f.id)} aria-pressed={prefs.focus === f.id}
            >{f.label}</button
          >
        {/each}
      </div>
    </div>
    <p class="hint">
      Panels never move. <b>Spotlight</b> lights the panels that matter in what you're doing (takeoff and landing,
      cruise, quantum, combat, on foot) and dims the rest. <b>Focus strip</b> adds one band at the top with that
      phase's numbers.
    </p>
  </section>
  <section>
    <h3>Look</h3>
    <label class="toggle">
      <input type="checkbox" bind:checked={prefs.effects} />
      <span><b>HUD effects</b><small>Glow, scanlines and animations</small></span>
    </label>
    <label class="toggle">
      <input type="checkbox" bind:checked={prefs.autoHide} />
      <span><b>Hide ship panels on foot</b><small>Otherwise they wait on standby</small></span>
    </label>
    <label class="toggle">
      <input type="checkbox" bind:checked={prefs.awake} disabled={wake !== "ok" && !prefs.awake} />
      <span
        ><b>Keep the screen awake</b><small
          >{wake === "insecure"
            ? "Needs the hub's https page; not available over your home network"
            : wake === "unsupported"
              ? "This browser can't (on iPhone and iPad: iOS 18.4 or later)"
              : awake.status === "refused"
                ? "The browser said no for now (low power mode?); tap the page to retry"
                : "For a phone or tablet beside the game, while this page is open"}</small
        ></span
      >
    </label>
    <div class="units">
      <span class="label">Speed in</span>
      <div class="seg">
        <button class:on={prefs.speedUnit === "ms"} onclick={() => (prefs.speedUnit = "ms")}>m/s</button>
        <button class:on={prefs.speedUnit === "kmh"} onclick={() => (prefs.speedUnit = "kmh")}>km/h</button>
      </div>
    </div>
  </section>

  <section>
    <h3>Activity</h3>
    <div class="units">
      <span class="label">Ships destroyed</span>
      <div class="seg" role="group" aria-label="Ships destroyed">
        {#each DESTROYED as n (n.id)}
          <button class:on={prefs.destroyed === n.id} onclick={() => (prefs.destroyed = n.id)} aria-pressed={prefs.destroyed === n.id}
            >{n.label}</button
          >
        {/each}
      </div>
    </div>
    <p class="hint">
      <b>Fleet</b>: ships fleet members destroy, and members' own ships lost. <b>Players</b> adds ships destroyed near a
      member where a player shot or lost one; <b>All</b> every one the game logs nearby, NPCs too. Nearby ones show small and
      grey.
    </p>
  </section>

  <HeaderAlerts alerts={prefs.alerts} self={selfAlerts} />

  <footer>
    <button class="reset" onclick={() => store.reset()}>Reset everything</button>
  </footer>
  {/if}
</aside>

<style>
  .drawer {
    position: fixed;
    top: 0;
    right: 0;
    bottom: 0;
    width: min(400px, 100vw);
    z-index: 30;
    overflow-y: auto;
    background: color-mix(in srgb, var(--bg) 92%, transparent);
    backdrop-filter: blur(14px);
    border-left: 1px solid var(--line-2);
    box-shadow: -20px 0 60px #0009;
    padding: 18px 18px 28px;
    display: grid;
    gap: 22px;
    align-content: start;
  }
  header {
    display: flex;
    justify-content: space-between;
    align-items: start;
    gap: 12px;
  }
  h2 {
    margin: 0;
    font-size: 1.25rem;
  }
  header p,
  .hint {
    margin: 2px 0 0;
    color: var(--text-3);
    font-size: 0.8rem;
  }
  h3 {
    margin: 0 0 10px;
    font-size: 0.72rem;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--text-3);
  }
  .hint {
    margin: -4px 0 10px;
  }
  button {
    cursor: pointer;
  }
  button:focus-visible,
  input:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }
  .tabs {
    display: flex;
    gap: 2px;
    margin-top: -8px;
  }
  .tabs button {
    flex: 1;
    border: 1px solid var(--line-2);
    background: var(--bg-2);
    color: var(--text-3);
    padding: 6px;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }
  .tabs button:first-child {
    border-radius: var(--radius-sm) 0 0 var(--radius-sm);
  }
  .tabs button:last-child {
    border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  }
  .tabs button.on {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--bg);
  }
  .done {
    border: 0;
    border-radius: 8px;
    padding: 7px 16px;
    font-weight: 700;
    background: var(--accent);
    color: var(--bg);
  }
  .presets {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }
  .preset {
    display: grid;
    gap: 2px;
    text-align: left;
    padding: 10px 12px;
    border-radius: var(--radius-sm);
    border: 1px solid var(--line-2);
    background: var(--panel);
  }
  .preset:hover {
    border-color: var(--accent);
  }
  .preset span {
    font-size: 0.75rem;
    color: var(--text-3);
  }
  .panels {
    list-style: none;
    padding: 0;
    margin: 0;
    display: grid;
    gap: 6px;
  }
  .panels li {
    display: grid;
    gap: 8px;
    padding: 10px 12px;
    border-radius: var(--radius-sm);
    border: 1px solid var(--line);
    background: var(--panel);
  }
  .panels li.hidden {
    opacity: 0.55;
  }
  .vis,
  .toggle {
    display: flex;
    gap: 10px;
    align-items: start;
    cursor: pointer;
  }
  .vis span,
  .toggle span {
    display: grid;
  }
  small {
    color: var(--text-3);
    font-size: 0.74rem;
  }
  input[type="checkbox"] {
    accent-color: var(--accent);
    width: 16px;
    height: 16px;
    margin-top: 2px;
  }
  .row {
    display: flex;
    gap: 6px;
    align-items: center;
  }
  .seg {
    display: inline-flex;
    border: 1px solid var(--line-2);
    border-radius: 8px;
    overflow: hidden;
  }
  .seg button {
    border: 0;
    background: var(--bg-2);
    padding: 4px 10px;
    font-size: 0.8rem;
    color: var(--text-2);
    border-right: 1px solid var(--line);
  }
  .seg button:last-child {
    border-right: 0;
  }
  .seg button.on {
    background: color-mix(in srgb, var(--accent) 22%, var(--bg-2));
    color: var(--text);
  }
  .seg button:disabled {
    opacity: 0.5;
    cursor: default;
  }
  .arrow {
    border: 1px solid var(--line-2);
    background: var(--bg-2);
    border-radius: 7px;
    width: 28px;
    height: 27px;
    color: var(--text-2);
  }
  .arrow:first-of-type {
    margin-left: auto;
  }
  .arrow:disabled {
    opacity: 0.35;
    cursor: default;
  }
  .themes {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 4px;
    margin: 6px 0 4px;
  }
  .theme {
    display: grid;
    grid-template-columns: 20px minmax(0, 1fr);
    column-gap: 8px;
    align-items: center;
    text-align: left;
    padding: 5px 8px;
    border: 1px solid var(--line-2);
    border-radius: var(--radius-sm);
    background: var(--bg-2);
    cursor: pointer;
  }
  .theme:hover {
    border-color: var(--text-3);
  }
  .theme.on {
    border-color: var(--accent);
    box-shadow: inset 0 0 0 1px var(--accent);
  }
  .theme .sw {
    grid-row: span 2;
    width: 20px;
    height: 20px;
    border-radius: 3px;
    border: 1px solid var(--line-2);
  }
  .theme b {
    font-size: 0.8rem;
  }
  .theme small {
    font-size: 0.66rem;
    color: var(--text-3);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .toggle {
    margin-bottom: 12px;
  }
  .units {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .reset {
    border: 1px solid color-mix(in srgb, var(--bad) 45%, transparent);
    color: var(--bad);
    background: transparent;
    border-radius: 8px;
    padding: 7px 14px;
  }
</style>
