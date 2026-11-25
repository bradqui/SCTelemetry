<script lang="ts">
  import type { Component } from "svelte";
  import { cubicOut } from "svelte/easing";
  import type { PanelCtx } from "../lib/context";
  import { eventPanel, eventTone } from "../lib/format";
  import { PANELS, type Layout, type PanelId, type Span } from "../lib/panels";
  import PanelFrame from "./PanelFrame.svelte";
  import EnvironmentPanel from "./panels/EnvironmentPanel.svelte";
  import EventsPanel from "./panels/EventsPanel.svelte";
  import FlightPanel from "./panels/FlightPanel.svelte";
  import FuelPanel from "./panels/FuelPanel.svelte";
  import HeadingPanel from "./panels/HeadingPanel.svelte";
  import MissionPanel from "./panels/MissionPanel.svelte";
  import PowerPanel from "./panels/PowerPanel.svelte";
  import ShipPanel from "./panels/ShipPanel.svelte";
  import ShipStatusPanel from "./panels/ShipStatusPanel.svelte";
  import TrendsPanel from "./panels/TrendsPanel.svelte";
  import VitalsPanel from "./panels/VitalsPanel.svelte";
  import WarningsPanel from "./panels/WarningsPanel.svelte";
  import WeaponsPanel from "./panels/WeaponsPanel.svelte";
  import WingmatesPanel from "./panels/WingmatesPanel.svelte";

  let {
    ctx,
    layout,
    editing = false,
    spotlight = null,
  }: {
    ctx: PanelCtx;
    layout: Layout;
    editing?: boolean;
    /** Spotlight: the panels that matter in this flight phase (the rest dim). */
    spotlight?: PanelId[] | null;
  } = $props();

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const COMPONENTS: Record<PanelId, Component<{ ctx: any }>> = {
    heading: HeadingPanel,
    flight: FlightPanel,
    ship: ShipPanel,
    warnings: WarningsPanel,
    status: ShipStatusPanel,
    trends: TrendsPanel,
    fuel: FuelPanel,
    power: PowerPanel,
    weapons: WeaponsPanel,
    vitals: VitalsPanel,
    environment: EnvironmentPanel,
    mission: MissionPanel,
    events: EventsPanel,
    wingmates: WingmatesPanel,
  };

  // The same array until the set of panels really changes. A new one every frame (ctx.ship
  // is a new object each snapshot) made Svelte re-measure and restart the slide animation
  // 17 times a second, so a 220 ms move crept on for seconds after sitting down.
  let shown: Layout = [];
  const visible = $derived.by(() => {
    const inShip = !!ctx.ship;
    const next = layout.filter(
      (s) =>
        !s.hidden &&
        !(s.id === "wingmates" && ctx.wing === undefined) && // the hub's pages: not yours to show
        !(s.id === "wingmates" && ctx.wing === null && !editing) && // not in a fleet: nothing to show
        (editing || !(PANELS[s.id].ship && !inShip && ctx.prefs.autoHide)),
    );
    if (next.length === shown.length && next.every((s, i) => s === shown[i])) return shown;
    shown = next;
    return next;
  });

  // No holes: a row that doesn't reach the edge (a panel hidden on foot, Wingmates with no
  // fleet) widens its last panel to fill it. Not while arranging, so spans stay as set.
  const fill = $derived.by(() => {
    const out = new Map<PanelId, number>();
    if (editing) return out;
    let used = 0;
    let row: typeof visible = [];
    const close = () => {
      const last = row[row.length - 1];
      if (last && used < 12) out.set(last.id, last.span + (12 - used));
      row = [];
      used = 0;
    };
    for (const slot of visible) {
      if (used + slot.span > 12) close();
      row.push(slot);
      used += slot.span;
    }
    close();
    return out;
  });

  /** Slide panels to their new places; no scaling (it stretches the text mid-move). */
  function slide(_node: Element, { from, to }: { from: DOMRect; to: DOMRect }) {
    const dx = from.left - to.left;
    const dy = from.top - to.top;
    if (!dx && !dy) return { duration: 0 };
    return {
      duration: 220,
      easing: cubicOut,
      css: (_t: number, u: number) => `transform: translate(${u * dx}px, ${u * dy}px)`,
    };
  }

  // Flash the panel an event is about.
  let pulses = $state<Partial<Record<PanelId, { n: number; tone: string }>>>({});
  let lastEvent: unknown = null;
  let primed = false;
  $effect(() => {
    const e = ctx.events[0];
    if (e === lastEvent) return;
    lastEvent = e;
    if (!primed) {
      primed = true; // don't flash for history loaded on connect
      return;
    }
    const id = e ? (eventPanel(e.kind) as PanelId | null) : null;
    if (e && id) pulses[id] = { n: (pulses[id]?.n ?? 0) + 1, tone: eventTone(e.kind, e.data) };
  });

  // -- editing

  function setSpan(id: PanelId, span: Span) {
    const slot = layout.find((s) => s.id === id);
    if (slot) slot.span = span;
  }
  function hide(id: PanelId) {
    const slot = layout.find((s) => s.id === id);
    if (slot) slot.hidden = true;
  }
  function move(id: PanelId, dir: -1 | 1) {
    const order = layout.filter((s) => !s.hidden);
    const i = order.findIndex((s) => s.id === id);
    const other = order[i + dir];
    if (!other) return;
    const a = layout.findIndex((s) => s.id === id);
    const b = layout.findIndex((s) => s.id === other.id);
    [layout[a], layout[b]] = [layout[b], layout[a]];
  }

  let dragging = $state<PanelId | null>(null);
  let lastTarget: PanelId | null = null;
  function dragOver(e: DragEvent, target: PanelId) {
    if (!dragging) return;
    e.preventDefault();
    if (target === dragging || target === lastTarget) return;
    lastTarget = target;
    const from = layout.findIndex((s) => s.id === dragging);
    const to = layout.findIndex((s) => s.id === target);
    const [slot] = layout.splice(from, 1);
    layout.splice(to, 0, slot);
  }
</script>

<div class="dash dash-grid" class:editing class:compact={ctx.compact}>
  {#each visible as slot (slot.id)}
    {@const info = PANELS[slot.id]}
    {@const Panel = COMPONENTS[slot.id]}
    <div
      class="cell s{fill.get(slot.id) ?? slot.span}"
      class:dragging={dragging === slot.id}
      animate:slide
      draggable={editing}
      ondragstart={(e) => {
        dragging = slot.id;
        lastTarget = null;
        e.dataTransfer?.setData("text/plain", slot.id);
      }}
      ondragover={(e) => dragOver(e, slot.id)}
      ondragend={() => (dragging = null)}
      role="listitem"
    >
      <PanelFrame
        title={info.title}
        span={slot.span}
        {editing}
        bare={slot.id === "heading"}
        lit={!editing && !!spotlight && spotlight.includes(slot.id)}
        dim={!editing && !!spotlight && !spotlight.includes(slot.id)}
        pulse={pulses[slot.id] ?? null}
        onSpan={(s) => setSpan(slot.id, s)}
        onHide={() => hide(slot.id)}
        onMove={(d) => move(slot.id, d)}
      >
        {#if info.ship && !ctx.ship}
          <p class="standby">Standby · not in a ship</p>
        {:else}
          <Panel {ctx} />
        {/if}
      </PanelFrame>
    </div>
  {/each}
</div>

<style>
  .dash {
    container: dash / inline-size;
    display: grid;
    grid-template-columns: repeat(12, minmax(0, 1fr));
    gap: var(--gap);
    align-items: stretch;
  }
  .cell {
    min-width: 0;
  }
  .s3 {
    grid-column: span 3;
  }
  .s4 {
    grid-column: span 4;
  }
  .s6 {
    grid-column: span 6;
  }
  .s8 {
    grid-column: span 8;
  }
  .s12 {
    grid-column: span 12;
  }
  .s5 {
    grid-column: span 5;
  }
  .s7 {
    grid-column: span 7;
  }
  .s9 {
    grid-column: span 9;
  }
  .s10 {
    grid-column: span 10;
  }
  .s11 {
    grid-column: span 11;
  }
  /* Narrower screens: small panels grow so nothing gets cramped. */
  @container dash (max-width: 1100px) {
    .dash:not(.compact) > .s3,
    .dash:not(.compact) > .s4,
    .dash:not(.compact) > .s5,
    .dash:not(.compact) > .s7 {
      grid-column: span 6;
    }
    .dash:not(.compact) > .s8,
    .dash:not(.compact) > .s9,
    .dash:not(.compact) > .s10,
    .dash:not(.compact) > .s11 {
      grid-column: span 12;
    }
  }
  @container dash (max-width: 640px) {
    .dash:not(.compact) > .cell {
      grid-column: span 12;
    }
  }
  @container dash (max-width: 360px) {
    .cell {
      grid-column: span 12;
    }
  }
  .dragging {
    opacity: 0.4;
  }
  .standby {
    margin: 0;
    color: var(--text-3);
    font-size: 0.85rem;
    letter-spacing: 0.04em;
  }
</style>
