import { LiveConnection } from "./live.svelte";
import { applyPatch } from "./patch";
import type { ReplayIndex, Snapshot, TelemetryEvent } from "./types";

// The cockpit view on a recording, with no agent: for the demo page on GitHub Pages. Plays
// demo-cockpit.json (tools/demo_cockpit.py: the bundled recordings through the real
// pipeline) and answers the replay bar's controls itself, so the real App runs unchanged.

export interface DemoCockpitData {
  step_ms: number;
  key_every: number;
  index: ReplayIndex;
  /** A snapshot every step_ms: {key: whole} every key_every steps, merge patches between. */
  steps: Record<string, unknown>[];
  events: TelemetryEvent[];
}

const MAX_EVENTS = 60;
const TICK_MS = 100;

/** Recorded times are ms from the start of the recording; make them clock times. */
function clocked<T>(value: T, base: number): T {
  if (Array.isArray(value)) return value.map((v) => clocked(v, base)) as T;
  if (value && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value)) {
      out[k] = (k === "t" || k === "since") && typeof v === "number" ? base + v : clocked(v, base);
    }
    return out as T;
  }
  return value;
}

export class DemoLive extends LiveConnection {
  #data: DemoCockpitData;
  #timer: ReturnType<typeof setInterval> | null = null;
  #pos = 0; // seconds
  #paused = false;
  #speed = 1;
  #step = -1; // the step whose snapshot is shown
  #raw: Snapshot | null = null;
  #base = 0; // clock ms at recording time 0, at the current speed's pace
  #last = 0;

  constructor(data: DemoCockpitData, opts: { at?: number; paused?: boolean } = {}) {
    super("ws://demo.invalid/ws");
    this.#data = data;
    this.#pos = Math.max(0, Math.min(opts.at ?? 0, data.index.duration));
    this.#paused = opts.paused ?? false;
    this.agentVersion = "demo";
    this.replay = true;
    this.replayIndex = data.index;
  }

  override start(): () => void {
    this.socket = "open";
    this.agent = { type: "state", connected: true, streaming: true, port: null, message: "Replaying", since: Date.now() };
    this.#jump(this.#pos);
    this.#status();
    this.#last = performance.now();
    this.#timer = setInterval(() => this.#tick(), TICK_MS);
    return () => this.stop();
  }

  override stop(): void {
    if (this.#timer) clearInterval(this.#timer);
    this.#timer = null;
  }

  override control(action: "play" | "pause" | "seek" | "speed" | "step", extra: Record<string, number> = {}): void {
    const dur = this.#data.index.duration;
    if (action === "play") {
      if (this.#pos >= dur - 0.05) this.#jump(0);
      this.#paused = false;
    } else if (action === "pause") {
      this.#paused = true;
    } else if (action === "speed") {
      this.#speed = Math.max(0.1, Math.min(Number(extra.speed) || 1, 16));
    } else if (action === "seek") {
      this.#jump(Number(extra.pos) || 0);
    } else if (action === "step") {
      this.#paused = true;
      const frames = Math.trunc(Number(extra.frames) || 1);
      const target = this.#pos + (frames * this.#data.step_ms) / 1000;
      if (frames < 0) this.#jump(target);
      else this.#advance(Math.min(target, dur));
    }
    this.#last = performance.now();
    this.#status();
  }

  #tick(): void {
    const now = performance.now();
    const dt = ((now - this.#last) / 1000) * this.#speed;
    this.#last = now;
    if (this.#paused) return;
    const dur = this.#data.index.duration;
    if (this.#pos + dt >= dur) {
      this.#jump(0); // loop, as the agent's replay does
      this.#status();
      return;
    }
    this.#advance(this.#pos + dt);
    if (Math.floor(this.#pos) !== Math.floor(this.#pos - dt)) this.#status(); // about once a second
  }

  /** Play forward to pos: the snapshots and the events on the way. */
  #advance(pos: number): void {
    const from = this.#pos;
    this.#pos = pos;
    this.#base = Date.now() - pos * 1000;
    const target = this.#stepAt(pos);
    for (let k = this.#step + 1; k <= target; k++) this.#apply(k);
    this.#step = Math.max(this.#step, target);
    const fresh = this.#data.events.filter((e) => e.t > from * 1000 && e.t <= pos * 1000);
    if (fresh.length) {
      this.events = [...fresh.reverse().map((e) => clocked(e, this.#base)), ...this.events].slice(0, MAX_EVENTS);
    }
    this.#publish();
  }

  /** Start fresh at pos (seek, step back, loop): the view clears, as with the agent. The
   * event list keeps this recording's events so far, so it isn't empty after a jump. */
  #jump(pos: number): void {
    const dur = this.#data.index.duration;
    pos = Math.max(0, Math.min(pos, dur));
    this.#pos = pos;
    this.#base = Date.now() - pos * 1000;
    const target = this.#stepAt(pos);
    const key = target - (target % this.#data.key_every);
    this.#raw = null;
    for (let k = key; k <= target; k++) this.#apply(k);
    this.#step = target;
    const chapter = [...this.#data.index.chapters].reverse().find((c) => c.start <= pos);
    const since = (chapter?.start ?? 0) * 1000;
    this.events = this.#data.events
      .filter((e) => e.t >= since && e.t <= pos * 1000)
      .reverse()
      .slice(0, MAX_EVENTS)
      .map((e) => clocked(e, this.#base));
    this.resets++;
    this.#publish();
  }

  #stepAt(pos: number): number {
    return Math.max(0, Math.min(Math.floor((pos * 1000) / this.#data.step_ms), this.#data.steps.length - 1));
  }

  #apply(k: number): void {
    const s = this.#data.steps[k];
    if (!s) return;
    if ("key" in s) this.#raw = s.key as Snapshot;
    else if (Object.keys(s).length) this.#raw = applyPatch(this.#raw, s) as Snapshot;
  }

  #publish(): void {
    this.snapshot = this.#raw ? clocked(this.#raw, this.#base) : null;
  }

  #status(): void {
    const chapters = this.#data.index.chapters;
    let chapter = 0;
    for (let i = 0; i < chapters.length; i++) if (chapters[i].start <= this.#pos) chapter = i;
    this.replayStatus = { pos: this.#pos, paused: this.#paused, speed: this.#speed, loop: true, chapter };
    this.replayAt = performance.now();
  }
}
