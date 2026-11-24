// Which of your fleets the cockpit page shows (the fleet view and the Wingmates panel), when
// you're in more than one (one per org's hub). Remembered in this browser; falls back to
// the first fleet that's connected when the saved one isn't there.
import type { UplinkStatus } from "./types";

const KEY = "ft.fleet.hub";

export interface FleetChoice {
  hub: string;
  label: string;
  state: UplinkStatus["state"];
}

function hostOf(url: string): string {
  try {
    return new URL(url).host;
  } catch {
    return url;
  }
}

class FleetPick {
  /** Your fleets that are sending, from the agent (App keeps this up to date). */
  choices = $state.raw<FleetChoice[]>([]);
  #wanted = $state<string | null>(null);

  constructor() {
    try {
      this.#wanted = localStorage.getItem(KEY);
    } catch {
      /* storage unavailable */
    }
  }

  /** The fleet to show: the one you picked, else the first connected, else the first. */
  get hub(): string | null {
    const c = this.choices;
    if (this.#wanted && c.some((f) => f.hub === this.#wanted)) return this.#wanted;
    return (c.find((f) => f.state === "connected") ?? c[0])?.hub ?? null;
  }

  pick(hub: string): void {
    this.#wanted = hub;
    try {
      localStorage.setItem(KEY, hub);
    } catch {
      /* fine */
    }
  }

  setFrom(uplinks: Record<string, UplinkStatus>): void {
    this.choices = Object.values(uplinks)
      .filter((u) => u.hub && u.state !== "unlinked")
      .map((u) => ({ hub: u.hub, label: u.org || hostOf(u.hub), state: u.state }))
      .sort((a, b) => a.label.localeCompare(b.label));
  }
}

export const fleetPick = new FleetPick();
