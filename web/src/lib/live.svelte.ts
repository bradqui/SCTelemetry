import type { AgentState, Snapshot, TelemetryEvent } from "./types";

const MAX_EVENTS = 40;

/** WebSocket to the agent's /ws, reconnecting with backoff. Reactive via Svelte runes. */
export class LiveConnection {
  socket = $state<"connecting" | "open" | "closed">("connecting");
  agent = $state<AgentState | null>(null);
  snapshot = $state<Snapshot | null>(null);
  events = $state<TelemetryEvent[]>([]);
  agentVersion = $state<string | null>(null);

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
    }
  }
}
