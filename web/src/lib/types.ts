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
