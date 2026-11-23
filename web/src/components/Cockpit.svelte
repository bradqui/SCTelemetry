<script lang="ts">
  import type { Ship, Weapons } from "../lib/types";
  import { altitude, heading, num, speed, titleCase } from "../lib/format";
  import Annunciators from "./Annunciators.svelte";
  import Bar from "./Bar.svelte";
  import Readout from "./Readout.svelte";

  let { ship, weapons, compact = false }: { ship: Ship; weapons: Weapons | null; compact?: boolean } =
    $props();

  const f = $derived(ship.flight);
  const alt = $derived(altitude(f.alt));
  const gunsReady = $derived(weapons ? weapons.guns.filter((g) => g.ready).length : 0);
  const gunsTotal = $derived(weapons?.guns.length ?? 0);

  const POWER_ORDER: [string, string][] = [
    ["powerplants", "Power plant"],
    ["engines", "Engines"],
    ["shield_generators", "Shield gen"],
    ["shield_emitters", "Emitters"],
    ["weapons", "Weapons"],
    ["coolers", "Coolers"],
    ["life_support", "Life support"],
    ["sensors", "Sensors"],
    ["gravity_generators", "Gravity"],
  ];

  const shieldsNote = $derived(
    ship.shields.powered === true ? "Up · level n/a" : ship.shields.powered === false ? "Down" : "No data",
  );
  const gearTransit = $derived(ship.gear === "deploying" || ship.gear === "retracting");
  const gForce = $derived(f.g == null ? null : f.g);
</script>

{#if compact}
  <section class="compact">
    <div class="c-row">
      <Readout label="Speed" value={speed(f.speed)} unit="m/s" size="lg" />
      <Readout label="Alt" value={alt.value} unit={alt.unit} size="lg" tone={f.alt == null ? "dim" : ""} />
      <Readout label="Hdg" value={heading(f.heading)} unit="°" size="lg" />
    </div>
    <Annunciators lights={ship.lights} compact />
    <div class="c-bars">
      <Bar label="Hull" value={ship.hull} empty="n/a" />
      <Bar label="Shields" value={ship.shields.level} empty={shieldsNote} tone={ship.shields.level == null ? (ship.shields.powered ? "accent" : "muted") : "auto"} />
      <Bar label="Hydrogen" value={f.h2_fuel} empty="—" />
      <Bar label="Boost" value={f.boost_reserve} tone="accent" empty="—" />
    </div>
    <div class="chips">
      {#if gunsTotal}<span class="chip" class:on={gunsReady === gunsTotal} class:warn={gunsReady < gunsTotal}>Guns {gunsReady}/{gunsTotal}</span>{/if}
      {#each weapons?.countermeasures ?? [] as cm (cm.type)}
        <span class="chip" class:bad={cm.count === 0}>{titleCase(cm.type)} {cm.count}</span>
      {/each}
      {#if ship.gear}<span class="chip" class:warn={gearTransit} class:pulse={gearTransit}>Gear {ship.gear}</span>{/if}
    </div>
  </section>
{:else}
  <section class="cockpit">
    <div class="panel flight">
      <span class="label">Flight</span>
      <div class="flight-main">
        <Readout label="Speed" value={speed(f.speed)} unit="m/s" size="xl" tone={f.boost_engaged ? "accent" : ""} />
        <div class="flight-side">
          <Readout label="Altitude" value={alt.value} unit={alt.unit} size="lg" tone={f.alt == null ? "dim" : ""} />
          <Readout label="Heading" value={heading(f.heading)} unit="°" size="lg" />
          <Readout label="Vertical" value={num(f.vsi, 0)} unit="m/s" size="lg" />
          <Readout
            label="G-force"
            value={num(gForce, 1)}
            unit="g"
            size="lg"
            tone={gForce != null && gForce > 9 ? "bad" : gForce != null && gForce > 5 ? "warn" : ""}
          />
        </div>
      </div>
      <div class="chips">
        <span class="chip" class:on={f.cruise}>Cruise</span>
        <span class="chip" class:on={f.g_safe} class:warn={f.g_safe === false}>G-safe</span>
        <span class="chip" class:on={f.coupled} class:warn={f.coupled === false}>
          {f.coupled === false ? "Decoupled" : "Coupled"}
        </span>
        <span class="chip" class:on={f.prox_assist}>Prox assist</span>
        <span class="chip" class:on={f.boost_engaged}>Boost</span>
        {#if f.atmo_density != null}<span class="chip off">Atmo {num(f.atmo_density, 2)}</span>{/if}
      </div>
    </div>

    <div class="panel warnings">
      <span class="label">Warnings</span>
      <Annunciators lights={ship.lights} />
      <div class="chips gear">
        <span class="chip" class:on={ship.landed} class:off={!ship.landed}>{ship.landed ? "Landed" : "Flying"}</span>
        {#if ship.gear}
          <span class="chip" class:warn={gearTransit} class:pulse={gearTransit} class:on={ship.gear === "deployed"}>
            Gear {ship.gear}
          </span>
        {/if}
      </div>
    </div>

    <div class="panel status">
      <span class="label">Ship status</span>
      <div class="bars">
        <Bar label="Hull" value={ship.hull} empty="No data from game" />
        <Bar
          label="Shields"
          value={ship.shields.level}
          empty={shieldsNote}
          tone={ship.shields.level == null ? (ship.shields.powered ? "accent" : "muted") : "auto"}
        />
        <Bar label="Hydrogen" value={f.h2_fuel} empty={ship.power.engines === false ? "Engines off" : "—"} />
        <Bar label="Quantum fuel" value={f.qt_fuel} empty="Not reported" tone="accent" />
        <Bar label="Boost reserve" value={f.boost_reserve} tone="accent" empty="—" />
      </div>
    </div>

    <div class="panel power">
      <span class="label">Power</span>
      <div class="power-grid">
        {#each POWER_ORDER as [key, name] (key)}
          {@const on = ship.power[key]}
          {#if on !== undefined}
            <div class="pw" class:on>
              <span class="dot"></span>{name}
            </div>
          {/if}
        {/each}
      </div>
    </div>

    <div class="panel weapons">
      <span class="label">Weapons</span>
      {#if weapons}
        <div class="w-top">
          <Readout
            label="Guns ready"
            value="{gunsReady}/{gunsTotal}"
            size="lg"
            tone={gunsTotal && gunsReady < gunsTotal ? "warn" : ""}
          />
          <span class="chip" class:on={weapons.gimbals_locked} class:off={!weapons.gimbals_locked}>
            Gimbals {weapons.gimbals_locked ? "locked" : "free"}
          </span>
        </div>
        <ul class="guns">
          {#each weapons.guns as gun, i (i)}
            <li class:ready={gun.ready} class:unpowered={!gun.powered}>
              <span class="dot"></span><span class="gname">{gun.name.replace(/_/g, " ")}</span>
              <span class="gstate">{!gun.powered ? "off" : gun.ready ? "ready" : "not ready"}</span>
            </li>
          {/each}
        </ul>
        <div class="chips">
          {#each weapons.countermeasures as cm (cm.type)}
            <span class="chip" class:bad={cm.count === 0}>{titleCase(cm.type)} <b class="num">{cm.count}</b></span>
          {/each}
        </div>
      {:else}
        <p class="muted">No weapons data for this seat.</p>
      {/if}
    </div>
  </section>
{/if}

<style>
  .cockpit {
    display: grid;
    gap: var(--gap);
    grid-template-columns: repeat(12, minmax(0, 1fr));
  }
  .flight {
    grid-column: span 7;
  }
  .warnings {
    grid-column: span 5;
  }
  .status {
    grid-column: span 5;
  }
  .power {
    grid-column: span 3;
  }
  .weapons {
    grid-column: span 4;
  }
  @media (max-width: 1180px) {
    .flight,
    .warnings {
      grid-column: span 12;
    }
    .status {
      grid-column: span 6;
    }
    .power {
      grid-column: span 6;
    }
    .weapons {
      grid-column: span 12;
    }
  }
  @media (max-width: 720px) {
    .status,
    .power {
      grid-column: span 12;
    }
  }

  .flight-main {
    display: grid;
    grid-template-columns: minmax(0, 1.1fr) minmax(0, 2fr);
    gap: 18px 24px;
    align-items: end;
  }
  .flight-side {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 12px;
  }
  @media (max-width: 860px) {
    .flight-main {
      grid-template-columns: 1fr;
    }
    .flight-side {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }

  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 7px;
    margin-top: 16px;
  }
  .gear {
    margin-top: 14px;
  }
  .pulse {
    animation: pulse 0.9s ease-in-out infinite;
  }

  .bars {
    display: grid;
    gap: 14px;
  }

  .power-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
    gap: 7px;
  }
  .pw {
    display: flex;
    align-items: center;
    gap: 9px;
    padding: 8px 10px;
    border-radius: var(--radius-sm);
    border: 1px solid var(--line);
    background: var(--bg-2);
    color: var(--text-3);
    font-size: 0.86rem;
    font-weight: 550;
  }
  .pw.on {
    color: var(--text);
    border-color: #3ddc9733;
  }
  .pw.on .dot {
    color: var(--good);
    box-shadow: 0 0 8px var(--good);
  }

  .w-top {
    display: flex;
    justify-content: space-between;
    align-items: end;
    gap: 10px;
  }
  .guns {
    list-style: none;
    padding: 0;
    margin: 14px 0 0;
    display: grid;
    gap: 5px;
  }
  .guns li {
    display: flex;
    align-items: center;
    gap: 9px;
    font-size: 0.85rem;
    color: var(--text-2);
  }
  .guns li .dot {
    color: var(--warn);
  }
  .guns li.ready .dot {
    color: var(--good);
  }
  .guns li.unpowered {
    color: var(--text-3);
  }
  .guns li.unpowered .dot {
    color: var(--line-2);
  }
  .gname {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-family: var(--mono);
    font-size: 0.78rem;
  }
  .gstate {
    font-size: 0.72rem;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-3);
  }
  .muted {
    color: var(--text-3);
    margin: 0;
  }

  .compact {
    display: grid;
    gap: 12px;
  }
  .c-row {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 10px;
  }
  .c-bars {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px 14px;
  }
  .compact .chips {
    margin-top: 0;
  }
</style>
