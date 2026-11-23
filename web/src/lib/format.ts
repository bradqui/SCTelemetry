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
};

export function eventText(kind: string, data: Record<string, unknown>): string {
  return (EVENT_TEXT[kind] ?? (() => titleCase(kind)))(data);
}

export function eventTone(kind: string, data: Record<string, unknown>): "info" | "good" | "warn" | "bad" {
  if (kind === "warning_on") return String(data.level).startsWith("major") ? "bad" : "warn";
  if (["hull_threshold", "fuel_threshold", "downed", "dead"].includes(kind)) return "bad";
  if (["warning_off", "landed", "game_start", "respawn"].includes(kind)) return "good";
  return "info";
}
