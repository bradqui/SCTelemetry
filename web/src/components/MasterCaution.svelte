<script lang="ts">
  import { slide } from "svelte/transition";
  import type { Level, LightKey } from "../lib/types";

  let { lights }: { lights: Partial<Record<LightKey, Level>> } = $props();

  const NAMES: Record<string, string> = {
    pwr: "Power",
    wpn: "Weapons",
    thr: "Thrusters",
    shld: "Shields",
    cool: "Cooling",
    qdrv: "Quantum drive",
    radr: "Radar",
    prox: "Proximity",
    hit: "Taking hits",
    misl: "Missile lock",
  };

  const major = $derived(Object.entries(lights).filter(([, l]) => l?.startsWith("major")).map(([k]) => k));
  const minor = $derived(Object.entries(lights).filter(([, l]) => l?.startsWith("minor")).map(([k]) => k));
  const active = $derived(major.length ? major : minor);
  const level = $derived(major.length ? "warning" : "caution");
</script>

{#if active.length}
  <div class="banner {level}" role="alert" transition:slide={{ duration: 180 }}>
    <span class="tag">{level === "warning" ? "Master warning" : "Master caution"}</span>
    <span class="what">{active.map((k) => NAMES[k] ?? k.toUpperCase()).join(" · ")}</span>
  </div>
{/if}

<style>
  .banner {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 8px 16px;
    border-radius: var(--radius-sm);
    font-weight: 650;
    min-width: 0;
  }
  .caution {
    background: color-mix(in srgb, var(--warn) 16%, var(--bg));
    border: 1px solid var(--warn);
    color: var(--warn);
  }
  .warning {
    background: color-mix(in srgb, var(--bad) 18%, var(--bg));
    border: 1px solid var(--bad);
    color: #ffd6da;
    animation: alarm 1s steps(1) infinite;
  }
  @keyframes alarm {
    50% {
      background: color-mix(in srgb, var(--bad) 40%, var(--bg));
    }
  }
  .tag {
    font-family: var(--mono);
    font-size: 0.78rem;
    font-weight: 800;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    padding: 2px 8px;
    border-radius: 5px;
    color: var(--bg);
    background: currentColor;
    flex: none;
  }
  .warning .tag {
    background: var(--bad);
    color: #fff;
  }
  .caution .tag {
    background: var(--warn);
  }
  .what {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
</style>
