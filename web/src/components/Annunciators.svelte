<script lang="ts">
  import { LIGHT_KEYS, type Level, type LightKey } from "../lib/types";

  let { lights, compact = false }: { lights: Partial<Record<LightKey, Level>>; compact?: boolean } =
    $props();

  const NAMES: Record<LightKey, string> = {
    pwr: "Power",
    wpn: "Weapons",
    thr: "Thrusters",
    shld: "Shields",
    cool: "Cooling",
    qdrv: "Quantum",
    radr: "Radar",
    prox: "Proximity",
    hit: "Hit",
    misl: "Missile",
  };
</script>

<div class="grid" class:compact role="list" aria-label="Warning lights">
  {#each LIGHT_KEYS as key (key)}
    {@const level = lights[key] ?? "off"}
    <div class="light {level}" role="listitem" title="{NAMES[key]}: {level.replace('_', ' ')}">
      <span class="code">{key.toUpperCase()}</span>
      {#if !compact}<span class="name">{NAMES[key]}</span>{/if}
    </div>
  {/each}
</div>

<style>
  .grid {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 4px;
  }
  .light {
    display: grid;
    place-items: center;
    gap: 1px;
    padding: 5px 2px 4px;
    min-height: var(--tile-h, 0px);
    border-radius: var(--radius-sm);
    border: 1px solid var(--line);
    background: var(--bg-2);
    color: var(--text-3);
    transition:
      background 0.15s,
      color 0.15s,
      border-color 0.15s;
  }
  @container panel (max-width: 330px) {
    .name {
      display: none;
    }
    .light {
      padding: 8px 2px;
    }
  }
  .compact .light {
    padding: 7px 2px;
  }
  .code {
    font-family: var(--mono);
    font-weight: 700;
    font-size: var(--tile-code, 0.8rem);
    letter-spacing: 0.06em;
  }
  .name {
    font-size: 0.54rem;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    opacity: 0.8;
  }
  .nominal {
    color: var(--good);
    border-color: color-mix(in srgb, var(--good) 25%, transparent);
    background: color-mix(in srgb, var(--good) 7%, transparent);
  }
  .minor,
  .minor_flashing {
    color: var(--bg);
    background: var(--warn);
    border-color: var(--warn);
    box-shadow: 0 0 18px color-mix(in srgb, var(--warn) 33%, transparent);
  }
  .major,
  .major_flashing {
    color: #fff;
    background: var(--bad);
    border-color: var(--bad);
    box-shadow: 0 0 22px color-mix(in srgb, var(--bad) 40%, transparent);
  }
  .minor_flashing,
  .major_flashing {
    animation: flash 0.6s steps(1) infinite;
  }
</style>
