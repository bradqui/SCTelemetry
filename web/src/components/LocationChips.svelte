<script lang="ts">
  // Where someone is, in game terms: zone chips, then labelled system / jurisdiction / server.
  import { shardLabel } from "../lib/format";

  interface Where {
    armistice: boolean | null;
    restricted: boolean | null;
    private: boolean | null;
    monitored: boolean | null;
    comms: boolean | null;
    jurisdiction: string | null;
    system: string | null;
    shard: string | null;
  }

  let {
    loc,
    server = true,
    sameServer = false,
    place = null,
  }: { loc: Where; server?: boolean; sameServer?: boolean; place?: string | null } = $props();
  const shard = $derived(shardLabel(loc.shard));
</script>

<div class="where" aria-label="Location">
  {#if place}<span class="place" title="Where, from the game's log: the landing area, or the planet or moon">{place}</span>{/if}
  {#if loc.armistice}<span class="z good" title="Armistice zone: weapons are disabled">Armistice</span>{/if}
  {#if loc.restricted}<span class="z bad" title="Restricted area">Restricted</span>{/if}
  {#if loc.private}<span class="z warn" title="Private property">Private</span>{/if}
  {#if loc.comms === false}
    <span class="z warn" title="The local comm array is down: crimes aren't reported">Comms down</span>
  {:else if loc.monitored === false}
    <span class="z warn" title="Outside monitored space">Unmonitored</span>
  {/if}
  {#if loc.system}<span class="kv sys" title="Star system"><b>System</b><span>{loc.system}</span></span>{/if}
  {#if loc.jurisdiction}
    <span class="kv jur" title="Jurisdiction: whose laws apply here"><b>Jurisdiction</b><span>{loc.jurisdiction}</span></span>
  {/if}
  {#if server && shard}
    <span class="kv srv" class:same={sameServer} title="Server {loc.shard}{sameServer ? ' (same as yours)' : ''}"
      ><b>Server</b><span class="mono">{shard}</span></span
    >
  {/if}
</div>

<style>
  .where {
    display: flex;
    align-items: center;
    gap: 4px;
    min-width: 0;
    flex: 0 10 auto; /* in the top bar: gives way before the ship's name and the alarm */
    overflow: hidden;
    white-space: nowrap;
  }
  .place {
    font-weight: 700;
    color: var(--text);
    margin-right: 4px;
    overflow: hidden;
    text-overflow: ellipsis;
    min-width: 0;
  }
  .z,
  .kv {
    display: inline-flex;
    align-items: center;
    height: 20px;
    box-sizing: border-box;
    line-height: 1;
    border-radius: var(--radius-chip);
    flex: none;
  }
  .z {
    font-size: 0.64rem;
    font-weight: 800;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    padding: 0 6px;
    border: 1px solid currentColor;
  }
  .z.good {
    color: var(--good);
    background: color-mix(in srgb, var(--good) 12%, transparent);
  }
  .z.warn {
    color: var(--warn);
    background: color-mix(in srgb, var(--warn) 12%, transparent);
  }
  .z.bad {
    color: var(--bad);
    background: color-mix(in srgb, var(--bad) 14%, transparent);
  }
  .kv {
    border: 1px solid var(--line-2);
    overflow: hidden;
    min-width: 0;
    flex: 0 1 auto;
  }
  .kv > b,
  .kv > span {
    display: flex;
    align-items: center;
    height: 100%;
    padding: 0 6px;
  }
  .kv > b {
    font-size: 0.58rem;
    font-weight: 800;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--text-3);
    background: var(--bg-2);
    border-right: 1px solid var(--line-2);
    flex: none;
  }
  .kv > span {
    font-size: 0.72rem;
    font-weight: 650;
    color: var(--text);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    min-width: 0;
    display: block;
    line-height: 18px;
  }
  .kv > span.mono {
    font-family: var(--mono);
    font-size: 0.68rem;
    color: var(--text-2);
  }
  .kv.same {
    border-color: color-mix(in srgb, var(--good) 55%, transparent);
  }
  .kv.same > b {
    color: var(--good);
  }
  @media (max-width: 1100px) {
    .srv {
      display: none;
    }
  }
  @media (max-width: 760px) {
    .sys,
    .jur {
      display: none;
    }
  }
</style>
