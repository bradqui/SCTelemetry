// Mirrors shared/fleet_shared/models.py (schema v1). Keep the two in step.

export type Level = "off" | "nominal" | "minor" | "minor_flashing" | "major" | "major_flashing";
export type Locomotion = "on_foot" | "eva" | "seated" | "unknown";
export type SeatRole = "pilot" | "copilot" | "gunner" | "crew";
export type Deployment = "retracted" | "deploying" | "deployed" | "retracting";

export interface Status {
  in_game: boolean;
  locomotion: Locomotion;
  seat: string | null;
  role: SeatRole | null;
}

export interface Shields {
  powered: boolean | null;
  level: number | null;
  faces: number[] | null;
}

export interface Flight {
  speed: number | null;
  alt: number | null;
  radar_alt: number | null;
  vsi: number | null;
  heading: number | null;
  g: number | null;
  g_max: number | null;
  atmo_density: number | null;
  h2_fuel: number | null;
  qt_fuel: number | null;
  boost_reserve: number | null;
  boost_engaged: boolean | null;
  cruise: boolean | null;
  g_safe: boolean | null;
  coupled: boolean | null;
  prox_assist: boolean | null;
  /** In quantum travel (inferred by the agent). */
  quantum: boolean | null;
}

export interface Ship {
  id: string;
  class: string;
  model: string;
  manufacturer: string | null;
  type: "spaceship" | "ground" | "gravlev" | "boat" | "unknown";
  hull: number | null;
  master_mode: "NAV" | "SCM" | null;
  powered: boolean | null;
  shields: Shields;
  power: Record<string, boolean>;
  lights: Partial<Record<LightKey, Level>>;
  gear: Deployment | null;
  landed: boolean | null;
  flight: Flight;
}

export const LIGHT_KEYS = ["pwr", "wpn", "thr", "shld", "cool", "qdrv", "radr", "prox", "hit", "misl"] as const;
export type LightKey = (typeof LIGHT_KEYS)[number];

export interface Gun {
  name: string;
  powered: boolean;
  ready: boolean;
}

export interface Weapons {
  gimbals_locked: boolean | null;
  guns: Gun[];
  countermeasures: { type: "decoy" | "noise" | "unknown"; count: number }[];
}

export interface Vitals {
  health: number | null;
  oxygen: number | null;
  hunger: number | null;
  thirst: number | null;
  body_temp: number | null;
  heart_rate: number | null;
  gravity: number | null;
  pressure: number | null;
  intoxication: number | null;
  environment: { temperature: number | null; breathable: boolean | null; radiation: number | null };
  injuries?: Injury[];
}

/** A plotted quantum route (within a star system), from Game.log. */
export interface Route {
  destination: string | null;
  state: "plotted" | "en_route" | "arrived" | "blocked";
  since: number;
}

export interface Location {
  armistice: boolean | null;
  jurisdiction: string | null;
  monitored: boolean | null;
  /** False while the local comm array is down. */
  comms: boolean | null;
  restricted: boolean | null;
  private: boolean | null;
  shard: string | null;
  system: string | null;
  route: Route | null;
}

export interface Mission {
  title: string | null;
  tags: string[];
  state: "active" | "complete" | "failed" | "abandoned";
  since: number;
  objective: string | null;
  objective_done: boolean;
  shared: boolean;
}

export interface Session {
  kills: number;
  ships_lost: number;
  deaths: number;
  incaps: number;
  contracts: number;
  failed: number;
  earned: number;
  quantum_trips: number;
  system_jumps: number;
}

export interface Injury {
  part: string;
  severity: "minor" | "moderate" | "severe" | string;
  tier: number;
}

export interface Snapshot {
  type: "snapshot";
  v: number;
  t: number;
  status: Status | null;
  ship: Ship | null;
  weapons: Weapons | null;
  vitals: Vitals | null;
  uec: number | null;
  /** From Game.log (absent when the agent can't read it). */
  location?: Location | null;
  missions?: Mission[] | null;
  session?: Session | null;
}

export interface TelemetryEvent {
  type: "event";
  v: number;
  t: number;
  kind: string;
  data: Record<string, unknown>;
}

export interface AgentState {
  type: "state";
  connected: boolean;
  streaming: boolean;
  port: number | null;
  message: string;
  since: number;
}

// Replay mode (`fleet_agent run --replay`) only.

export interface ReplayMarker {
  pos: number;
  kind: string;
  data: Record<string, unknown>;
}

export interface ReplayChapter {
  title: string;
  start: number;
  end: number;
}

export interface ReplayIndex {
  duration: number;
  frames: number;
  chapters: ReplayChapter[];
  markers: ReplayMarker[];
}

export interface ReplayStatus {
  pos: number;
  paused: boolean;
  speed: number;
  loop: boolean;
  chapter: number;
}
