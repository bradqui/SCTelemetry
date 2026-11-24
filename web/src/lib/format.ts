export const DASH = "—";

export function num(v: number | null | undefined, digits = 0): string {
  return v == null || !Number.isFinite(v) ? DASH : v.toFixed(digits);
}

export function pct(v: number | null | undefined): string {
  return v == null ? DASH : `${Math.round(v * 100)}%`;
}

export function speed(v: number | null | undefined): string {
  return v == null ? DASH : Math.round(Math.abs(v) < 0.5 ? 0 : v).toLocaleString();
}

/** Altitude: metres under 10 km, else km. null means "in space". */
export function altitude(v: number | null | undefined): { value: string; unit: string } {
  if (v == null) return { value: "SPACE", unit: "" };
  if (Math.abs(v) >= 10_000) return { value: (v / 1000).toFixed(1), unit: "km" };
  return { value: Math.round(v).toLocaleString(), unit: "m" };
}

export function heading(v: number | null | undefined): string {
  if (v == null) return DASH;
  const h = ((Math.round(v) % 360) + 360) % 360;
  return h.toString().padStart(3, "0");
}

export function temp(v: number | null | undefined): string {
  return v == null ? DASH : `${v.toFixed(v <= -100 || v >= 100 ? 0 : 1)}°C`;
}

export function ago(t: number, now: number): string {
  const s = Math.max(0, Math.round((now - t) / 1000));
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  return `${Math.floor(m / 60)}h ${m % 60}m ago`;
}

export function clock(t: number): string {
  return new Date(t).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function titleCase(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

const EVENT_TEXT: Record<string, (d: Record<string, unknown>) => string> = {
  game_start: () => "Telemetry started",
  game_exit: () => "Game closed",
  seat_enter: (d) => `Took the ${d.role ?? "seat"} seat`,
  seat_leave: (d) => `Left the ${d.role ?? ""} seat`.replace("  ", " "),
  ship_change: (d) => `Now in ${d.model ?? "another ship"}`,
  mode_change: (d) => `${d.mode} mode`,
  quantum_start: () => "Quantum jump",
  quantum_end: () => "Dropped out of quantum",
  quantum_route: (d) => `Route set: ${d.destination ?? "unknown"}`,
  quantum_arrived: (d) => (d.destination ? `Arrived at ${d.destination}` : "Arrived"),
  quantum_blocked: (d) => `Route obstructed${d.destination ? `: ${d.destination}` : ""}`,
  takeoff: () => "Took off",
  landed: () => "Landed",
  warning_on: (d) => `${String(d.light).toUpperCase()} warning`,
  warning_off: (d) => `${String(d.light).toUpperCase()} clear`,
  hull_threshold: (d) => `Hull below ${Math.round(Number(d.below) * 100)}%`,
  fuel_threshold: (d) => `Fuel below ${Math.round(Number(d.below) * 100)}%`,
  spawn: () => "Spawned",
  downed: () => "Downed",
  dead: () => "Died",
  respawn: () => "Respawned",
  // From Game.log
  qt_calibration: (d) => `${d.by} ${d.done ? "finished" : "started"} quantum calibration`,
  jump_start: (d) => `Entering jump point${d.system ? ` from ${d.system}` : ""}`,
  jump_end: (d) => `Jumped to ${d.system ?? "another system"}`,
  shard_join: () => "Joined a server",
  armistice_enter: () => "Entered armistice zone",
  armistice_leave: () => "Left armistice zone",
  jurisdiction: (d) => `${d.name} jurisdiction`,
  monitored_enter: () => "Entered monitored space",
  monitored_leave: () => "Left monitored space",
  comms_down: () => "Comm array down",
  comms_restored: () => "Comm array restored",
  restricted_enter: () => "Restricted area",
  restricted_leave: () => "Left restricted area",
  private_enter: () => "Entered private property",
  private_leave: () => "Left private property",
  contract_accepted: (d) => `Accepted: ${d.title}`,
  contract_shared: (d) => `Shared: ${d.title}`,
  contract_complete: (d) => `Completed: ${d.title}`,
  contract_failed: (d) => `Failed: ${d.title}`,
  contract_abandoned: (d) => `Abandoned: ${d.title}`,
  objective_new: (d) => `New objective: ${d.text}`,
  objective_complete: (d) => `Objective done: ${d.text}`,
  objective_withdrawn: (d) => `Objective withdrawn: ${d.text}`,
  objective_failed: (d) => `Objective failed: ${d.text}`,
  reward: (d) => `+${Number(d.auec).toLocaleString()} aUEC`,
  kill: (d) => `Destroyed ${d.npc === "hostile" ? "hostile " : ""}${d.target}`,
  vehicle_destroyed: (d) => `${d.target} destroyed by ${d.by}`,
  ship_lost: (d) => `Ship destroyed by ${d.by}`,
  death: (d) => `Killed by ${d.by}`,
  injury: (d) => `${titleCase(String(d.severity))} injury: ${d.part} (tier ${d.tier})`,
  healed: () => "Healed at a medical bed",
  incapacitated: () => "Incapacitated",
  // The game's own words: the same notification comes for arriving and for leaving.
  hangar_ready: () => "Hangar request completed",
  hangar_queue: () => "Waiting for a hangar",
  blueprint: (d) => `Blueprint: ${d.name}`,
};

export function eventText(kind: string, data: Record<string, unknown>): string {
  return (EVENT_TEXT[kind] ?? (() => titleCase(kind)))(data);
}

const BAD = new Set([
  "hull_threshold", "fuel_threshold", "downed", "dead", "ship_lost", "death", "incapacitated",
  "contract_failed", "objective_failed", "restricted_enter",
]);
const GOOD = new Set([
  "warning_off", "landed", "game_start", "respawn", "quantum_arrived", "kill", "contract_complete",
  "objective_complete", "reward", "healed", "hangar_ready", "armistice_enter", "comms_restored", "jump_end",
]);
const WARN = new Set([
  "quantum_blocked", "comms_down", "armistice_leave", "monitored_leave", "private_enter", "injury",
  "contract_abandoned", "objective_withdrawn",
]);

export function eventTone(kind: string, data: Record<string, unknown>): "info" | "good" | "warn" | "bad" {
  if (kind === "warning_on") return String(data.level).startsWith("major") ? "bad" : "warn";
  if (BAD.has(kind)) return "bad";
  if (GOOD.has(kind)) return "good";
  if (WARN.has(kind)) return "warn";
  return "info";
}

export type EventCategory = "flight" | "combat" | "mission" | "location" | "you";

export const CATEGORIES: { id: EventCategory; label: string }[] = [
  { id: "flight", label: "Flight" },
  { id: "combat", label: "Combat" },
  { id: "mission", label: "Contracts" },
  { id: "location", label: "Location" },
  { id: "you", label: "You" },
];

/** Grouping for the Activity panel's filters and colour rail. */
export function eventCategory(kind: string): EventCategory {
  if (["kill", "vehicle_destroyed", "ship_lost", "death", "hull_threshold"].includes(kind) || kind.startsWith("warning"))
    return "combat";
  if (kind.startsWith("contract") || kind.startsWith("objective") || kind === "reward") return "mission";
  if (
    ["shard_join", "jurisdiction", "comms_down", "comms_restored", "hangar_ready", "hangar_queue"].includes(kind) ||
    /^(armistice|monitored|restricted|private)_/.test(kind)
  )
    return "location";
  if (["injury", "healed", "incapacitated", "spawn", "downed", "dead", "respawn", "blueprint"].includes(kind) || kind.startsWith("seat"))
    return "you";
  return "flight";
}

/** Short server label: pub_use1b_13165946_150 -> "use1b · 150". */
export function shardLabel(shard: string | null | undefined): string | null {
  if (!shard) return null;
  const parts = shard.split("_");
  return parts.length >= 4 ? `${parts[1]} · ${parts[parts.length - 1]}` : shard;
}

/** Speed in the chosen unit. */
export function speedIn(v: number | null | undefined, unit: "ms" | "kmh"): { value: string; unit: string } {
  if (v == null) return { value: DASH, unit: unit === "kmh" ? "km/h" : "m/s" };
  return unit === "kmh" ? { value: speed(v * 3.6), unit: "km/h" } : { value: speed(v), unit: "m/s" };
}

/** A round scale maximum at or above v. */
export function niceMax(v: number, floor = 100): number {
  const steps = [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8];
  const target = Math.max(v, floor);
  const mag = 10 ** Math.floor(Math.log10(target));
  for (const s of steps) if (s * mag >= target) return s * mag;
  return 10 * mag;
}

/** "m:ss" or "h:mm:ss" for a replay position in seconds. */
export function duration(s: number): string {
  const t = Math.max(0, Math.floor(s));
  const h = Math.floor(t / 3600);
  const m = Math.floor((t % 3600) / 60);
  const sec = String(t % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${sec}` : `${m}:${sec}`;
}

/** Short relative time: "now", "12s", "4m", "1h". */
export function since(t: number, now: number): string {
  const s = Math.max(0, Math.round((now - t) / 1000));
  if (s < 3) return "now";
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  return `${Math.floor(s / 3600)}h`;
}

/** Which panel an event is about (it flashes when the event happens). */
export function eventPanel(kind: string): string | null {
  if (kind.startsWith("warning") || kind === "takeoff" || kind === "landed") return "warnings";
  if (kind === "hull_threshold") return "ship";
  if (kind === "fuel_threshold") return "fuel";
  if (kind === "mode_change" || kind.startsWith("quantum") || kind.startsWith("jump_")) return "flight";
  if (["spawn", "downed", "dead", "respawn", "injury", "healed", "incapacitated", "death"].includes(kind))
    return "vitals";
  if (kind.startsWith("seat") || kind === "ship_change" || kind === "ship_lost") return "ship";
  if (kind === "kill") return "weapons";
  if (kind.startsWith("contract") || kind.startsWith("objective") || kind === "reward") return "mission";
  return null;
}

/** Warning light names, as the header and roster spell them out. */
export const LIGHT_NAMES: Record<string, string> = {
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

export const ROLE_NAMES: Record<string, string> = {
  pilot: "Pilot",
  copilot: "Co-pilot",
  gunner: "Gunner",
  crew: "Crew",
};
