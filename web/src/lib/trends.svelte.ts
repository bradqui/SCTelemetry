import type { Snapshot } from "./types";

export interface Sample {
  t: number;
  speed: number | null;
  alt: number | null;
  g: number | null;
}

const EVERY_MS = 250;
export const WINDOW_S = 180;
const MAX = (WINDOW_S * 1000) / EVERY_MS;

/** A short rolling history of flight values for the trend charts. */
export class Trends {
  samples = $state.raw<Sample[]>([]);
  /** Highest speed in the window: sets the speed dial's scale. */
  peakSpeed = $state(0);
  #last = 0;

  push(snap: Snapshot | null): void {
    if (!snap || snap.t - this.#last < EVERY_MS) return;
    this.#last = snap.t;
    const f = snap.ship?.flight;
    const sample: Sample = { t: snap.t, speed: f?.speed ?? null, alt: f?.alt ?? null, g: f?.g ?? null };
    // Keep the window by time as well as count (replay jumps, pauses).
    const cutoff = snap.t - WINDOW_S * 1000;
    const next = this.samples.filter((s) => s.t >= cutoff && s.t <= snap.t).slice(-(MAX - 1));
    next.push(sample);
    this.samples = next;
    let peak = 0;
    for (const s of next) if (s.speed != null && s.speed > peak) peak = s.speed;
    this.peakSpeed = peak;
  }

  /** Start from the agent's history (a page opened mid-flight). */
  seed(rows: [number, number | null, number | null, number | null][]): void {
    this.samples = rows.slice(-MAX).map(([t, speed, alt, g]) => ({ t, speed, alt, g }));
    this.#last = this.samples.length ? this.samples[this.samples.length - 1].t : 0;
    this.peakSpeed = Math.max(0, ...this.samples.map((s) => s.speed ?? 0));
  }

  clear(): void {
    this.samples = [];
    this.peakSpeed = 0;
    this.#last = 0;
  }
}
