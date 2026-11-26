// A contract's objectives at a glance: which one's next, and how many are done.
import type { Mission, Objective } from "./types";

/** The first objective still open; else the last one set. */
export function currentObjective(m: Mission): Objective | null {
  return m.objectives.find((o) => o.state === "active") ?? m.objectives.at(-1) ?? null;
}

/** Done out of the ones that count (a withdrawn objective no longer does). */
export function objectiveCount(m: Mission): { done: number; total: number } {
  const counted = m.objectives.filter((o) => o.state !== "withdrawn");
  return { done: counted.filter((o) => o.state === "complete").length, total: counted.length };
}
