<script lang="ts">
  // The Focus strip (Settings → Flight phases): one fixed band at the top of the dashboard
  // with the numbers that matter in this phase. It never moves; only its content changes.
  import type { PanelCtx } from "../lib/context";
  import { altitude, LIGHT_NAMES, pct, placeText, speedIn } from "../lib/format";
  import { PHASE_NAMES, type Phase } from "../lib/phase";

  let { ctx, phase }: { ctx: PanelCtx; phase: Phase } = $props();

  const LIT = ["minor", "minor_flashing", "major", "major_flashing"];
  const items = $derived.by((): [string, string, string?][] => {
    const s = ctx.snap;
    const ship = s.ship;
    const f = ship?.flight;
    const v = s.vitals;
    const route = s.location?.route;
    const spd = speedIn(f?.speed ?? null, ctx.prefs.speedUnit);
    const place = placeText(s.location, { locomotion: s.status?.locomotion, landed: ship?.landed, quantum: f?.quantum });
    switch (phase) {
      case "foot":
        return [
          ["Health", pct(v?.health ?? null), v?.health != null && v.health < 0.5 ? "bad" : ""],
          ["Oxygen", pct(v?.oxygen ?? null), v?.oxygen != null && v.oxygen < 0.3 ? "bad" : ""],
          ["Where", place ?? "—"],
        ];
      case "landing": {
        const agl = f?.radar_alt;
        return [
          ["Above ground", agl == null ? "—" : `${Math.round(agl)} m`, agl != null && agl < 20 ? "warn" : ""],
          ["Vert speed", f?.vsi == null ? "—" : `${f.vsi > 0 ? "+" : ""}${f.vsi.toFixed(1)} m/s`, f?.vsi != null && f.vsi < -10 ? "warn" : ""],
          ["Gear", ship?.gear ? ship.gear[0].toUpperCase() + ship.gear.slice(1) : "—", ship?.gear === "retracted" ? "warn" : ""],
          ["Speed", `${spd.value} ${spd.unit}`],
        ];
      }
      case "cruise": {
        const alt = altitude(f?.alt ?? null);
        return [
          ["Speed", `${spd.value} ${spd.unit}`],
          ["Altitude", `${alt.value} ${alt.unit}`.trim()],
          ["Hydrogen", pct(f?.h2_fuel ?? null), f?.h2_fuel != null && f.h2_fuel < 0.25 ? "warn" : ""],
          [route?.destination ? "Route" : "Where", route?.destination ?? place ?? "—"],
        ];
      }
      case "quantum":
        return [
          ["Quantum to", route?.destination ?? "—"],
          ["Quantum fuel", f?.qt_fuel == null ? "—" : pct(f.qt_fuel)],
          ["Hydrogen", pct(f?.h2_fuel ?? null)],
        ];
      case "combat": {
        const lights = Object.entries(ship?.lights ?? {})
          .filter(([, lv]) => LIT.includes(lv ?? ""))
          .map(([k]) => LIGHT_NAMES[k] ?? k.toUpperCase());
        const w = s.weapons;
        const decoys = w?.countermeasures.find((c) => c.type.toLowerCase().includes("decoy"));
        return [
          ["Shields", ship?.shields.powered === false ? "Down" : ship?.shields.powered ? "Up" : "—", ship?.shields.powered === false ? "bad" : ""],
          ["Warnings", lights.length ? lights.join(" · ") : "None", lights.length ? "warn" : ""],
          ["Guns ready", w ? `${w.guns.filter((g) => g.ready).length} / ${w.guns.length}` : "—"],
          ["Decoys", decoys ? String(decoys.count) : "—", decoys?.count === 0 ? "bad" : ""],
        ];
      }
    }
  });
</script>

<section class="strip" aria-label="Focus: {PHASE_NAMES[phase]}">
  <span class="phase">{PHASE_NAMES[phase]}</span>
  <div class="items">
    {#each items as [label, value, tone] (label)}
      <div class="item">
        <span class="label">{label}</span>
        <b class="num {tone ?? ''}">{value}</b>
      </div>
    {/each}
  </div>
</section>

<style>
  .strip {
    display: flex;
    align-items: center;
    gap: 16px;
    min-height: 36px;
    padding: 4px 12px;
    border: var(--border-w, 1px) solid var(--accent);
    border-radius: var(--radius);
    background: linear-gradient(90deg, color-mix(in srgb, var(--accent) 12%, var(--panel)), var(--panel));
    overflow: hidden;
  }
  .phase {
    flex: none;
    font-family: var(--font-display);
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--bg);
    background: var(--accent);
    border-radius: var(--radius-chip);
    padding: 2px 8px;
  }
  .items {
    display: flex;
    flex-wrap: wrap;
    gap: 2px 26px;
    min-width: 0;
  }
  .item {
    display: flex;
    align-items: baseline;
    gap: 7px;
    min-width: 0;
  }
  .item .label {
    font-size: 0.6rem;
  }
  .item b {
    font-size: 1.05rem;
    font-weight: 700;
    line-height: 1.15;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .warn {
    color: var(--warn);
  }
  .bad {
    color: var(--bad);
  }
</style>
