import type { FleetConnection } from "./fleet.svelte";
import type { Prefs } from "./prefs.svelte";
import type { Trends } from "./trends.svelte";
import type { Ship, Snapshot, TelemetryEvent } from "./types";

/** Everything a panel may draw from. */
export interface PanelCtx {
  snap: Snapshot;
  ship: Ship | null;
  events: TelemetryEvent[];
  trends: Trends;
  prefs: Prefs;
  compact: boolean;
  /** Wall clock, ticking once a second (for "12s ago"). */
  now: number;
  /** Whose data this is, when it isn't yours (the fleet page): labels say their name. */
  who?: string;
  /** Your cockpit view, linked to a fleet: the fleet, relayed by the agent (Wingmates). */
  wing?: FleetConnection | null;
}

/** The same, for panels that only render in a ship. */
export type ShipCtx = PanelCtx & { ship: Ship };
