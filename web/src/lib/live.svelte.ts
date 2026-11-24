import type { AgentState, ReplayIndex, ReplayStatus, Snapshot, TelemetryEvent, UplinkStatus } from "./types";

const MAX_EVENTS = 60;

/** WebSocket to the agent's /ws, reconnecting with backoff. Reactive via Svelte runes. */
export class LiveConnection {
  socket = $state<"connecting" | "open" | "closed">("connecting");
  agent = $state<AgentState | null>(null);
  snapshot = $state.raw<Snapshot | null>(null);
  events = $state.raw<TelemetryEvent[]>([]);
  agentVersion = $state<string | null>(null);
  /** Bumped when the agent starts fresh (a replay jump): views drop their history. */
  resets = $state(0);

  /** Trend history the agent sent on connect: [t, speed, alt, g][]. */
  trendSeed = $state.raw<[number, number | null, number | null, number | null][]>([]);

  /** The agent's links to its fleets' hubs, by hub (empty: not in a fleet, or not sending). */
  uplinks = $state.raw<Record<string, UplinkStatus>>({});

  replay = $state(false);
  replayIndex = $state.raw<ReplayIndex | null>(null);
  replayStatus = $state.raw<ReplayStatus | null>(null);
  /** performance.now() when replayStatus arrived, to move the playhead smoothly between updates. */
  replayAt = 0;

  #ws: WebSocket | null = null;
  #retry = 500;
  #timer: ReturnType<typeof setTimeout> | null = null;
  #stopped = false;
  readonly url: string;

  constructor(url = LiveConnection.defaultUrl()) {
    this.url = url;
  }

  static defaultUrl(): string {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${location.host}/ws`;
  }

  start(): () => void {
    this.#stopped = false;
    this.#connect();
    return () => this.stop();
  }

  stop(): void {
    this.#stopped = true;
    if (this.#timer) clearTimeout(this.#timer);
    this.#ws?.close();
  }

  /** Replay controls. Ignored by the agent unless it is replaying. */
  control(action: "play" | "pause" | "seek" | "speed" | "step", extra: Record<string, number> = {}): void {
    if (this.#ws?.readyState === WebSocket.OPEN) {
      this.#ws.send(JSON.stringify({ type: "replay", action, ...extra }));
    }
  }

  /** Where the replay is now, in seconds, moving between status updates while playing. */
  replayPos(now = performance.now()): number {
    const s = this.replayStatus;
    if (!s) return 0;
    if (s.paused) return s.pos;
    const pos = s.pos + ((now - this.replayAt) / 1000) * s.speed;
    return Math.min(pos, this.replayIndex?.duration ?? pos);
  }

  #connect(): void {
    this.socket = "connecting";
    const ws = new WebSocket(this.url);
    this.#ws = ws;
    ws.onopen = () => {
      this.socket = "open";
      this.#retry = 500;
    };
    ws.onmessage = (msg) => this.#handle(JSON.parse(msg.data));
    ws.onclose = () => {
      this.socket = "closed";
      if (!this.#stopped) {
        this.#timer = setTimeout(() => this.#connect(), this.#retry);
        this.#retry = Math.min(this.#retry * 2, 8000);
      }
    };
  }

  #handle(msg: { type: string } & Record<string, unknown>): void {
    switch (msg.type) {
      case "hello":
        this.agentVersion = (msg.agent_version as string) ?? null;
        this.replay = msg.replay === true;
        break;
      case "state":
        this.agent = msg as unknown as AgentState;
        if (!this.agent.streaming) this.snapshot = null;
        break;
      case "snapshot":
        this.snapshot = msg as unknown as Snapshot;
        break;
      case "history":
        this.events = (msg.events as TelemetryEvent[]).slice(-MAX_EVENTS).reverse();
        break;
      case "event":
        this.events = [msg as unknown as TelemetryEvent, ...this.events].slice(0, MAX_EVENTS);
        break;
      case "trends":
        this.trendSeed = msg.samples as [number, number | null, number | null, number | null][];
        break;
      case "reset":
        // Keep showing the last snapshot until the next one (a frame away) so nothing flickers.
        this.events = [];
        this.resets++;
        break;
      case "uplink": {
        const u = msg as unknown as UplinkStatus;
        const next = { ...this.uplinks };
        if (u.state === "unlinked") delete next[u.hub];
        else next[u.hub] = u;
        this.uplinks = next;
        break;
      }
      case "replay_index":
        this.replayIndex = msg as unknown as ReplayIndex;
        break;
      case "replay":
        this.replayStatus = msg as unknown as ReplayStatus;
        this.replayAt = performance.now();
        break;
    }
  }
}
