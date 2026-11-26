<script lang="ts">
  import { onMount } from "svelte";
  import { fly } from "svelte/transition";
  import { duration, eventText, eventTone } from "../lib/format";
  import type { LiveConnection } from "../lib/live.svelte";
  import type { ReplayMarker } from "../lib/types";
  import EventIcon from "./EventIcon.svelte";

  let { live }: { live: LiveConnection } = $props();

  /** Land a few seconds before an event, so you see it happen. */
  const PREROLL = 4;
  const SPEEDS = [0.5, 1, 2, 4, 8];

  const index = $derived(live.replayIndex);
  const status = $derived(live.replayStatus);
  const dur = $derived(index?.duration || 1);
  const markers = $derived(index?.markers ?? []);

  let pos = $state(0);
  let scrub = $state<number | null>(null);
  let hover = $state<{ x: number; pos: number; marker: ReplayMarker | null } | null>(null);
  let listOpen = $state(false);
  let track = $state<HTMLElement>(null!);

  onMount(() => {
    let raf = 0;
    const tick = () => {
      pos = live.replayPos();
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  });

  const shown = $derived(scrub ?? pos);
  const chapterIdx = $derived.by(() => {
    const cs = index?.chapters ?? [];
    let i = 0;
    for (let k = 0; k < cs.length; k++) if (cs[k].start <= shown + 0.001) i = k;
    return i;
  });
  const chapter = $derived(index?.chapters[chapterIdx] ?? null);

  function chapterOf(p: number) {
    const cs = index?.chapters ?? [];
    let c = cs[0];
    for (const ch of cs) if (ch.start <= p) c = ch;
    return c;
  }

  function seek(p: number) {
    live.control("seek", { pos: Math.max(0, Math.min(dur, p)) });
  }
  function jump(m: ReplayMarker) {
    const ch = chapterOf(m.pos);
    seek(Math.max(ch?.start ?? 0, m.pos - PREROLL));
    if (status?.paused) live.control("play");
    listOpen = false;
  }
  function toggle() {
    live.control(status?.paused ? "play" : "pause");
  }
  function nextEvent() {
    const m = markers.find((m) => m.pos - PREROLL > pos + 0.3);
    if (m) jump(m);
  }
  function prevEvent() {
    const before = markers.filter((m) => m.pos - PREROLL < pos - 1.5);
    const m = before[before.length - 1];
    if (m) jump(m);
    else seek(0);
  }

  function posAt(clientX: number): number {
    const r = track.getBoundingClientRect();
    return Math.max(0, Math.min(1, (clientX - r.left) / r.width)) * dur;
  }
  function nearestMarker(p: number): ReplayMarker | null {
    const r = track.getBoundingClientRect();
    const tol = (8 / r.width) * dur; // within 8 px
    let best: ReplayMarker | null = null;
    for (const m of markers) {
      if (Math.abs(m.pos - p) <= tol && (!best || Math.abs(m.pos - p) < Math.abs(best.pos - p))) best = m;
    }
    return best;
  }
  function onDown(e: PointerEvent) {
    track.setPointerCapture(e.pointerId);
    const p = posAt(e.clientX);
    const m = nearestMarker(p);
    if (m) {
      jump(m);
      return;
    }
    scrub = p;
  }
  function onMove(e: PointerEvent) {
    const p = posAt(e.clientX);
    const r = track.getBoundingClientRect();
    // the tip's left is in layout px; the pointer is on screen (they differ when zoomed)
    hover = { x: ((e.clientX - r.left) / r.width) * track.offsetWidth, pos: p, marker: scrub == null ? nearestMarker(p) : null };
    if (scrub != null) scrub = p;
  }
  function onUp() {
    if (scrub != null) {
      seek(scrub);
      // Hold the scrub position until the agent confirms, so the head doesn't jump back.
      const target = scrub;
      setTimeout(() => {
        if (scrub === target) scrub = null;
      }, 250);
    }
  }

  function onKey(e: KeyboardEvent) {
    const t = e.target as HTMLElement;
    if (t && (t.tagName === "INPUT" || t.tagName === "SELECT" || t.tagName === "TEXTAREA")) return;
    if (e.key === " ") {
      e.preventDefault();
      toggle();
    } else if (e.key === "ArrowRight") {
      e.preventDefault();
      if (e.shiftKey) seek(pos + 10);
      else nextEvent();
    } else if (e.key === "ArrowLeft") {
      e.preventDefault();
      if (e.shiftKey) seek(pos - 10);
      else prevEvent();
    } else if (e.key === ".") live.control("step", { frames: 1 });
    else if (e.key === ",") live.control("step", { frames: -1 });
  }

  const grouped = $derived(
    (index?.chapters ?? []).map((c) => ({
      chapter: c,
      markers: markers.filter((m) => m.pos >= c.start && m.pos <= c.end + 0.001),
    })),
  );
</script>

<svelte:window onkeydown={onKey} />

{#if index && status}
  <div class="replay" role="region" aria-label="Replay controls">
    <div class="controls">
      <span class="badge">Replay</span>
      <button class="btn" onclick={prevEvent} title="Previous event (←)" aria-label="Previous event">
        <svg viewBox="0 0 16 16"><path d="M4 3v10M13 3 6 8l7 5z" /></svg>
      </button>
      <button class="btn play" onclick={toggle} title="Play/pause (Space)" aria-label={status.paused ? "Play" : "Pause"}>
        {#if status.paused}
          <svg viewBox="0 0 16 16"><path d="M5 3l8 5-8 5z" /></svg>
        {:else}
          <svg viewBox="0 0 16 16"><path d="M5 3v10M11 3v10" /></svg>
        {/if}
      </button>
      <button class="btn" onclick={nextEvent} title="Next event (→)" aria-label="Next event">
        <svg viewBox="0 0 16 16"><path d="M12 3v10M3 3l7 5-7 5z" /></svg>
      </button>
      {#if status.paused}
        <button class="btn small" onclick={() => live.control("step", { frames: -1 })} title="Back one frame (,)">−1f</button>
        <button class="btn small" onclick={() => live.control("step", { frames: 1 })} title="Forward one frame (.)">+1f</button>
      {/if}
      <span class="time num">{duration(shown)} <span>/ {duration(dur)}</span></span>
      <span class="chapter">{chapter?.title ?? ""}</span>
      <span class="spacer"></span>
      <div class="list-wrap">
        <button class="btn text" onclick={() => (listOpen = !listOpen)} aria-expanded={listOpen}>
          Events <b class="num">{markers.length}</b>
        </button>
        {#if listOpen}
          <div class="list" transition:fly={{ y: 8, duration: 160 }}>
            {#each grouped as g (g.chapter.start)}
              <div class="group">
                <button class="gtitle" onclick={() => { seek(g.chapter.start); listOpen = false; }}>
                  {g.chapter.title}<span class="num">{duration(g.chapter.start)}</span>
                </button>
                {#each g.markers as m, i (i)}
                  <button class="item {eventTone(m.kind, m.data)}" onclick={() => jump(m)}>
                    <EventIcon kind={m.kind} />
                    <span>{eventText(m.kind, m.data)}</span>
                    <span class="num">{duration(m.pos)}</span>
                  </button>
                {/each}
              </div>
            {/each}
          </div>
        {/if}
      </div>
      <select
        class="speed"
        value={status.speed}
        onchange={(e) => live.control("speed", { speed: Number(e.currentTarget.value) })}
        aria-label="Speed"
      >
        {#each SPEEDS as s (s)}<option value={s}>{s}×</option>{/each}
      </select>
    </div>

    <div
      class="track"
      bind:this={track}
      onpointerdown={onDown}
      onpointermove={onMove}
      onpointerup={onUp}
      onpointerleave={() => (hover = null)}
      role="slider"
      tabindex="-1"
      aria-label="Replay position"
      aria-valuemin={0}
      aria-valuemax={dur}
      aria-valuenow={Math.round(shown)}
    >
      {#each index.chapters as c, i (c.start)}
        <div
          class="chap"
          class:current={i === chapterIdx}
          style:left="{(c.start / dur) * 100}%"
          style:width="{((c.end - c.start) / dur) * 100}%"
        >
          <span>{c.title}</span>
        </div>
      {/each}
      <div class="played" style:width="{(shown / dur) * 100}%"></div>
      {#each markers as m, i (i)}
        <span class="marker {eventTone(m.kind, m.data)}" style:left="{(m.pos / dur) * 100}%"></span>
      {/each}
      <div class="head" style:left="{(shown / dur) * 100}%"></div>
      {#if hover}
        <div class="tip" style:left="{hover.x}px">
          {#if hover.marker}
            <b>{eventText(hover.marker.kind, hover.marker.data)}</b> · {duration(hover.marker.pos)} · click to jump
          {:else}
            {chapterOf(hover.pos)?.title} · {duration(hover.pos)}
          {/if}
        </div>
      {/if}
    </div>
    <p class="keys">Space play/pause · ← → previous/next event · Shift+← → 10 s · , . one frame</p>
  </div>
{/if}

<style>
  .replay {
    position: fixed;
    left: 50%;
    bottom: 10px;
    transform: translateX(-50%);
    width: min(1440px - 32px, calc(calc(100vw / var(--z, 1)) - 20px));
    z-index: 20;
    padding: 10px 14px 6px;
    border-radius: var(--radius);
    border: 1px solid var(--line-2);
    background: color-mix(in srgb, var(--bg) 88%, transparent);
    backdrop-filter: blur(14px);
    box-shadow: 0 10px 40px #000a;
  }
  .controls {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
  }
  .badge {
    font-size: 0.66rem;
    font-weight: 800;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--bg);
    background: var(--nav);
    padding: 3px 7px;
    border-radius: 5px;
    margin-right: 4px;
  }
  .btn {
    height: 30px;
    min-width: 30px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 8px;
    border: 1px solid var(--line-2);
    background: var(--bg-2);
    color: var(--text);
    cursor: pointer;
    padding: 0 8px;
    font-size: 0.78rem;
  }
  .btn:hover,
  .btn:focus-visible,
  .speed:focus-visible {
    border-color: var(--accent);
    outline: none;
  }
  .btn.play {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--bg);
    min-width: 38px;
  }
  .btn svg {
    width: 14px;
    height: 14px;
  }
  .btn path {
    fill: currentColor;
    stroke: currentColor;
    stroke-width: 1.6;
    stroke-linejoin: round;
    stroke-linecap: round;
  }
  .btn.small {
    color: var(--text-2);
  }
  .btn.text {
    white-space: nowrap;
  }
  .btn.text b {
    margin-left: 5px;
    color: var(--accent);
  }
  .time {
    margin-left: 8px;
    font-weight: 700;
    font-size: 0.9rem;
  }
  .time span {
    color: var(--text-3);
    font-weight: 500;
  }
  .chapter {
    color: var(--text-2);
    font-size: 0.85rem;
    margin-left: 8px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    min-width: 0;
  }
  .spacer {
    flex: 1;
  }
  .speed {
    height: 30px;
    border-radius: 8px;
    border: 1px solid var(--line-2);
    background: var(--bg-2);
    color: var(--text);
    padding: 0 6px;
  }

  .track {
    position: relative;
    height: 34px;
    margin-top: 10px;
    cursor: pointer;
    touch-action: none;
  }
  .chap {
    position: absolute;
    top: 12px;
    height: 10px;
    border-left: 2px solid var(--bg);
    background: var(--line);
    border-radius: 3px;
  }
  .chap:nth-child(even) {
    background: var(--line-2);
  }
  .chap span {
    position: absolute;
    top: -15px;
    left: 4px;
    font-size: 0.62rem;
    color: var(--text-3);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: calc(100% - 6px);
  }
  .chap.current span {
    color: var(--text);
  }
  .played {
    position: absolute;
    left: 0;
    top: 12px;
    height: 10px;
    border-radius: 3px;
    background: color-mix(in srgb, var(--accent) 45%, transparent);
    pointer-events: none;
  }
  .marker {
    position: absolute;
    top: 9px;
    width: 4px;
    height: 16px;
    margin-left: -2px;
    border-radius: var(--radius-sm);
    background: var(--accent);
    box-shadow: 0 0 0 1.5px var(--bg);
    pointer-events: none;
  }
  .marker.good {
    background: var(--good);
  }
  .marker.warn {
    background: var(--warn);
  }
  .marker.bad {
    background: var(--bad);
  }
  .head {
    position: absolute;
    top: 4px;
    width: 3px;
    height: 26px;
    margin-left: -1.5px;
    border-radius: var(--radius-sm);
    background: var(--text);
    box-shadow: 0 0 10px var(--accent);
    pointer-events: none;
  }
  .tip {
    position: absolute;
    bottom: 38px;
    transform: translateX(-50%);
    white-space: nowrap;
    font-size: 0.76rem;
    padding: 4px 9px;
    border-radius: 6px;
    background: var(--bg);
    border: 1px solid var(--line-2);
    pointer-events: none;
  }
  .keys {
    margin: 2px 0 0;
    font-size: 0.66rem;
    color: var(--text-3);
    text-align: right;
  }
  @container page (max-width: 640px) {
    .keys,
    .chapter {
      display: none;
    }
  }

  .list-wrap {
    position: relative;
  }
  .list {
    position: absolute;
    right: 0;
    bottom: 40px;
    width: min(360px, calc(calc(100vw / var(--z, 1)) - 30px));
    max-height: min(calc(60vh / var(--z, 1)), 520px);
    overflow-y: auto;
    padding: 8px;
    border-radius: var(--radius-sm);
    border: 1px solid var(--line-2);
    background: var(--bg);
    box-shadow: 0 10px 40px #000c;
  }
  .group + .group {
    margin-top: 8px;
  }
  .gtitle,
  .item {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 9px;
    border: 0;
    background: none;
    color: var(--text);
    cursor: pointer;
    text-align: left;
    padding: 6px 8px;
    border-radius: 6px;
  }
  .gtitle {
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--text-2);
  }
  .gtitle span,
  .item span:last-child {
    margin-left: auto;
    color: var(--text-3);
    font-size: 0.75rem;
    letter-spacing: 0;
  }
  .item {
    font-size: 0.86rem;
    color: var(--accent);
  }
  .item span:nth-child(2) {
    color: var(--text);
  }
  .item.good {
    color: var(--good);
  }
  .item.warn {
    color: var(--warn);
  }
  .item.bad {
    color: var(--bad);
  }
  .gtitle:hover,
  .item:hover,
  .item:focus-visible,
  .gtitle:focus-visible {
    background: var(--panel-2);
    outline: none;
  }
</style>
