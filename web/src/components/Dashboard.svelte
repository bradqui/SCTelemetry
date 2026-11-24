<script lang="ts">
  import type { Component } from "svelte";
  import { flip } from "svelte/animate";
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
  import TrendsPanel from "./panels/TrendsPanel.svelte";
  import VitalsPanel from "./panels/VitalsPanel.svelte";
  import WarningsPanel from "./panels/WarningsPanel.svelte";
  import WeaponsPanel from "./panels/WeaponsPanel.svelte";

  let { ctx, layout, editing = false }: { ctx: PanelCtx; layout: Layout; editing?: boolean } = $props();

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const COMPONENTS: Record<PanelId, Component<{ ctx: any }>> = {
    heading: HeadingPanel,
    flight: FlightPanel,
    ship: ShipPanel,
    warnings: WarningsPanel,
    trends: TrendsPanel,
    fuel: FuelPanel,
    power: PowerPanel,
    weapons: WeaponsPanel,
    vitals: VitalsPanel,
    environment: EnvironmentPanel,
    mission: MissionPanel,
    events: EventsPanel,
  };

  const visible = $derived(
    layout.filter((s) => !s.hidden && (editing || !(PANELS[s.id].ship && !ctx.ship && ctx.prefs.autoHide))),
  );

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
      class="cell s{slot.span}"
      class:dragging={dragging === slot.id}
      animate:flip={{ duration: 220 }}
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
  /* Narrower screens: small panels grow so nothing gets cramped. */
  @container dash (max-width: 1100px) {
    .dash:not(.compact) > .s3,
    .dash:not(.compact) > .s4 {
      grid-column: span 6;
    }
    .dash:not(.compact) > .s8 {
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
