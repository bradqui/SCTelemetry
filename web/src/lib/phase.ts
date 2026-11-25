// What you're doing right now, for the dashboard's optional emphasis (Settings → Flight
// phases): Spotlight lights the panels that matter in this phase and dims the rest; the
// Focus strip is one fixed band at the top with this phase's numbers. Panels never move.
import type { PanelId } from "./panels";
import type { Snapshot } from "./types";

export type Phase = "foot" | "landing" | "cruise" | "quantum" | "combat";
export type Focus = "off" | "spot" | "strip" | "both";

export const PHASE_NAMES: Record<Phase, string> = {
  foot: "On foot",
  landing: "Takeoff and landing",
  cruise: "Cruise",
  quantum: "Quantum",
  combat: "Combat",
};

/** The panels Spotlight lights in each phase. */
export const SPOTLIGHT: Record<Phase, PanelId[]> = {
  foot: ["vitals", "environment", "mission", "events"],
  landing: ["flight", "status", "warnings", "fuel"],
  cruise: ["flight", "heading", "fuel", "mission", "events"],
  quantum: ["flight", "fuel", "events"],
  combat: ["status", "ship", "warnings", "weapons", "power"],
};

const LIT = new Set(["minor", "minor_flashing", "major", "major_flashing"]);
const COMBAT_HOLD_MS = 20_000;

/** Combat is sticky: it stays for a while after the last hit, missile or shield warning. */
export function inCombat(snap: Snapshot): boolean {
  const l = snap.ship?.lights;
  if (!l) return false;
  return LIT.has(l.hit ?? "off") || LIT.has(l.misl ?? "off") || (l.shld ?? "").startsWith("major");
}

export function phaseOf(snap: Snapshot | null, combatUntil: number, now: number): Phase | null {
  if (!snap) return null;
  const ship = snap.ship;
  if (!ship || snap.status?.locomotion !== "seated") return "foot";
  if (ship.flight.quantum) return "quantum";
  if (now < combatUntil) return "combat";
  const agl = ship.flight.radar_alt;
  if (ship.landed || ship.gear === "deployed" || ship.gear === "deploying" || (agl != null && agl < 300)) {
    return "landing";
  }
  return "cruise";
}

export { COMBAT_HOLD_MS };
