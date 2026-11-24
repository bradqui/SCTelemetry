import { applyPatch } from "./patch";
import type { FleetEvent, Me, MemberSummary, Snapshot, TelemetryEvent } from "./types";

const MAX_EVENTS = 200;

/** The hub's /ws/view: the roster, fleet events, and the member you have open.
 * ``local``: the same stream relayed by the agent on this PC (/ws/fleet), for the fleet
 * view in the cockpit page; the agent signs in to the hub with the PC's link. */
export class FleetConnection {
  socket = $state<"connecting" | "open" | "closed">("connecting");
  me = $state.raw<Me | null>(null);
  /** The org's name (from the hub's hello). */
  org = $state<string | null>(null);
  /** Local only: this PC isn't linked to a fleet. */
  unlinked = $state(false);
  /** Local only: why the agent couldn't reach the hub. */
  problem = $state<string | null>(null);
  readonly local: boolean;
  /** Local: which of this PC's fleets (its hub); none: the agent's first. */
  readonly hub: string | null;

  constructor(opts: { local?: boolean; hub?: string | null } = {}) {
    this.local = !!opts.local;
    this.hub = opts.hub ?? null;
  }
  roster = $state.raw<Record<string, MemberSummary>>({});
  events = $state.raw<FleetEvent[]>([]);
  /** The member open in the detail view, and their full state. */
  focus = $state<string | null>(null);
  focusSnap = $state.raw<Snapshot | null>(null);
  /** Set when the hub refuses us (signed out elsewhere, role removed). */
  signedOut = $state(false);

  #ws: WebSocket | null = null;
  #retry = 500;
  #timer: ReturnType<typeof setTimeout> | null = null;
  #stopped = false;

  start(): () => void {
    // Started already (the cockpit's fleet view starts it to learn who you are, then the
    // board starts it again): one socket.
    if (this.#ws && !this.#stopped) return () => this.stop();
    this.#stopped = false;
    this.#connect();
    return () => this.stop();
  }

  stop(): void {
    this.#stopped = true;
    if (this.#timer) clearTimeout(this.#timer);
    this.#ws?.close();
  }

  open(memberId: string | null): void {
    if (memberId === this.focus) return;
    this.focus = memberId;
    this.focusSnap = null;
    this.#send({ type: "focus", member: memberId });
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

  /** A member's events as the dashboard panels expect them, newest first. */
  eventsOf(memberId: string): TelemetryEvent[] {
    const out: TelemetryEvent[] = [];
    for (let i = this.events.length - 1; i >= 0 && out.length < 60; i--) {
      const e = this.events[i];
      if (e.member === memberId) out.push(this.#asPanelEvent(e));
    }
    return out;
  }

  #send(msg: unknown): void {
    if (this.#ws?.readyState === WebSocket.OPEN) this.#ws.send(JSON.stringify(msg));
  }

  #connect(): void {
    this.socket = "connecting";
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    const path = this.local ? `/ws/fleet${this.hub ? `?hub=${encodeURIComponent(this.hub)}` : ""}` : "/ws/view";
    const ws = new WebSocket(`${proto}//${location.host}${path}`);
    this.#ws = ws;
    let opened = false;
    ws.onopen = () => {
      opened = true;
      this.socket = "open";
      this.#retry = 500;
      if (this.focus) this.#send({ type: "focus", member: this.focus });
    };
    ws.onmessage = (msg) => this.#handle(JSON.parse(msg.data));
    ws.onclose = () => {
      this.socket = "closed";
      if (this.#stopped) return;
      if (this.local) {
        // The agent says why (unlinked, hub down); try again now and then.
        this.#timer = setTimeout(() => this.#connect(), this.unlinked ? 15000 : this.#retry);
        this.#retry = Math.min(this.#retry * 2, 10000);
        return;
      }
      if (!opened) {
        // Refused before it opened: maybe we're signed out. Ask the hub.
        fetch("/api/mode")
          .then((r) => r.json())
          .then((m) => {
            if (!m.me) this.signedOut = true;
          })
          .catch(() => {});
      }
      this.#timer = setTimeout(() => this.#connect(), this.#retry);
      this.#retry = Math.min(this.#retry * 2, 10000);
    };
  }

  #handle(msg: { type: string } & Record<string, unknown>): void {
    switch (msg.type) {
      case "hello":
        this.me = msg.me as Me;
        this.org = (msg.org as string | undefined) ?? null;
        this.unlinked = false;
        this.problem = null;
        break;
      case "unlinked":
        this.unlinked = true;
        break;
      case "error":
        this.problem = String(msg.message ?? "Can't reach the fleet hub.");
        break;
      case "roster":
        this.roster = msg.members as Record<string, MemberSummary>;
        break;
      case "roster_delta":
        this.roster = applyPatch(this.roster, msg.patch as Record<string, unknown>);
        break;
      case "history":
        this.events = (msg.events as FleetEvent[]).slice(-MAX_EVENTS);
        break;
      case "event": {
        const { type: _t, ...e } = msg;
        this.events = [...this.events.slice(-(MAX_EVENTS - 1)), e as unknown as FleetEvent];
        break;
      }
      case "member":
        if (msg.id === this.focus) this.focusSnap = (msg.snapshot as Snapshot | null) ?? null;
        break;
      case "member_delta":
        if (msg.id === this.focus && this.focusSnap) {
          this.focusSnap = applyPatch(this.focusSnap, msg.patch as Record<string, unknown>);
        }
        break;
    }
  }
}
