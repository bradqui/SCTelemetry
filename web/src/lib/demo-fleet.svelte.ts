import { applyPatch } from "./patch";
import type { FleetEvent, Me, MemberSummary, Snapshot, TelemetryEvent } from "./types";

// A fleet that plays recorded telemetry on a loop instead of talking to a hub: for the
// showcase page, where there's no server. Same shape as FleetConnection, so the real
// fleet page runs on it unchanged. Data: tools/demo_fleet.py (real recordings through
// the real agent pipeline and hub roster code, as merge patches every step_ms).

interface DemoMember {
  id: string;
  name: string;
  /** Snapshot patches, one per step (the first is the whole state). Empty: no telemetry. */
  snaps: Record<string, unknown>[];
  /** Roster row patches, one per step (static members: one row). */
  rows: Record<string, unknown>[];
  /** Events and the step they happen at. */
  events: { i: number; kind: string; data: Record<string, unknown> }[];
}

export interface DemoData {
  step_ms: number;
  me: string;
  org: string;
  members: DemoMember[];
}

interface Playing {
  m: DemoMember;
  i: number;
  /** Clock time the current loop began: recorded times are relative to it. */
  start: number;
  snap: Snapshot | null;
  row: MemberSummary;
}

const MAX_EVENTS = 200;
const WARM_STEPS = 120; // start 30 s in, with that history already in the activity feeds

/** Recorded times are ms from the loop start; make them clock times. */
function clocked<T>(value: T, start: number): T {
  if (Array.isArray(value)) return value.map((v) => clocked(v, start)) as T;
  if (value && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value)) {
      out[k] = (k === "t" || k === "since" || k === "last_seen") && typeof v === "number" ? start + v : clocked(v, start);
    }
    return out as T;
  }
  return value;
}

export class DemoFleet {
  socket = $state<"connecting" | "open" | "closed">("open");
  me = $state.raw<Me | null>(null);
  roster = $state.raw<Record<string, MemberSummary>>({});
  events = $state.raw<FleetEvent[]>([]);
  focus = $state<string | null>(null);
  focusSnap = $state.raw<Snapshot | null>(null);
  signedOut = $state(false);

  #data: DemoData;
  #playing: Playing[] = [];
  #timer: ReturnType<typeof setInterval> | null = null;
  #tick = 0;

  constructor(data: DemoData) {
    this.#data = data;
    const me = data.members.find((m) => m.id === data.me);
    this.me = me ? { id: me.id, name: me.name, avatar: null } : null;
  }

  start(): () => void {
    const step = this.#data.step_ms;
    const now = Date.now();
    this.#playing = this.#data.members.map((m) => ({
      m,
      i: -1,
      start: now,
      snap: null,
      row: m.rows[0] as unknown as MemberSummary,
    }));
    // Warm up: play the first WARM_STEPS as if they'd already happened.
    for (let k = 0; k < WARM_STEPS; k++) this.#step(now - (WARM_STEPS - k) * step);
    this.#publish();
    this.#timer = setInterval(() => {
      this.#step(Date.now());
      this.#publish();
    }, step);
    return () => this.stop();
  }

  stop(): void {
    if (this.#timer) clearInterval(this.#timer);
    this.#timer = null;
  }

  open(memberId: string | null): void {
    this.focus = memberId;
    this.#publishFocus();
  }

  /** Each event is converted once, so panels see the same object every time: the Activity
   * panel animates and the dashboard flashes a panel only for an event that's really new. */
  #panelEvents = new WeakMap<FleetEvent, TelemetryEvent>();
  #asPanelEvent(e: FleetEvent): TelemetryEvent {
    let out = this.#panelEvents.get(e);
    if (!out) {
      out = { type: "event", v: 1, t: e.t, kind: e.kind, data: e.data };
      this.#panelEvents.set(e, out);
    }
    return out;
  }

  eventsOf(memberId: string): TelemetryEvent[] {
    const out: TelemetryEvent[] = [];
    for (let i = this.events.length - 1; i >= 0 && out.length < 60; i--) {
      const e = this.events[i];
      if (e.member === memberId) out.push(this.#asPanelEvent(e));
    }
    return out;
  }

  #step(clock: number): void {
    const step = this.#data.step_ms;
    const fresh: FleetEvent[] = [];
    for (const p of this.#playing) {
      const n = p.m.snaps.length;
      if (!n) continue;
      p.i = (p.i + 1) % n;
      if (p.i === 0) {
        p.start = clock;
        p.snap = null;
        p.row = {} as MemberSummary;
      }
      p.snap = applyPatch(p.snap, p.m.snaps[p.i]) as Snapshot;
      p.row = applyPatch(p.row, p.m.rows[p.i]) as MemberSummary;
      for (const e of p.m.events) {
        if (e.i === p.i) fresh.push({ member: p.m.id, t: p.start + e.i * step, kind: e.kind, data: e.data });
      }
    }
    if (fresh.length) this.events = [...this.events, ...fresh].slice(-MAX_EVENTS);
    this.#tick++;
  }

  #publish(): void {
    if (this.#tick % 2 === 0 || !Object.keys(this.roster).length) {
      const roster: Record<string, MemberSummary> = {};
      for (const p of this.#playing) {
        const row = p.m.snaps.length ? clocked(p.row, p.start) : clocked(p.row, Date.now());
        roster[p.m.id] = row;
      }
      this.roster = roster;
    }
    this.#publishFocus();
  }

  #publishFocus(): void {
    const p = this.#playing.find((x) => x.m.id === this.focus);
    this.focusSnap = p?.snap ? clocked(p.snap, p.start) : null;
  }
}
