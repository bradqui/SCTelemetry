/** Which warning lights go in the headers: your cockpit's top bar and the fleet header.
 * Each browser chooses (Customize → Header alerts): per light, as a warning (major) and as
 * a caution (minor), for each header. A light shows in a header only at a level ticked
 * for it there. The cards and dashboards always show every light, as the game does. */

/** The game's ten warning lights, in the order the Warnings panel shows them. */
export const LIGHTS = ["hit", "radr", "misl", "prox", "shld", "thr", "wpn", "pwr", "cool", "qdrv"] as const;

export interface AlertPick {
  /** Lights shown as a warning when they're major. */
  warning: string[];
  /** Lights shown as a caution when they're minor. */
  caution: string[];
}

export interface Alerts {
  /** Your top bar (the cockpit view). */
  self: AlertPick;
  /** The fleet header: each member's lights, held a second by the hub. */
  fleet: AlertPick & {
    /** "Badly hurt": severe injury or health under 30 %. */
    hurt: boolean;
    /** Your own lights in the fleet header too. */
    me: boolean;
  };
}

export function defaultAlerts(): Alerts {
  return {
    // Your own: everything, as the game's panel does.
    self: { warning: [...LIGHTS], caution: [...LIGHTS] },
    // The fleet: only calls for help: getting hit, hostiles on radar. Cautions last
    // (thruster damage stays minor for minutes after a fight) and fill the header.
    fleet: { warning: ["hit", "radr"], caution: [], hurt: true, me: true },
  };
}

function pick(raw: unknown, fallback: AlertPick): AlertPick {
  const r = (raw ?? {}) as Partial<AlertPick>;
  const ok = (v: unknown, d: string[]) =>
    Array.isArray(v) ? v.filter((x): x is string => typeof x === "string" && (LIGHTS as readonly string[]).includes(x)) : d;
  return { warning: ok(r.warning, fallback.warning), caution: ok(r.caution, fallback.caution) };
}

/** Saved settings, checked; ``caution`` is the old on/off "Master caution" setting. */
export function loadAlerts(raw: unknown, caution?: unknown): Alerts {
  const d = defaultAlerts();
  if (!raw || typeof raw !== "object") {
    if (caution === false) d.self = { warning: [], caution: [] };
    return d;
  }
  const r = raw as Partial<Alerts>;
  const fleet = (r.fleet ?? {}) as Partial<Alerts["fleet"]>;
  return {
    self: pick(r.self, d.self),
    fleet: {
      ...pick(r.fleet, d.fleet),
      hurt: typeof fleet.hurt === "boolean" ? fleet.hurt : d.fleet.hurt,
      me: typeof fleet.me === "boolean" ? fleet.me : d.fleet.me,
    },
  };
}

/** A ship's lit lights as alerts: light -> "major" | "minor". The hit light counts as major
 * whatever it shows; THR in NAV is the quantum drive, not a fault. (Python: alert_lights.) */
export function alertLights(lights: Partial<Record<string, string | null>>, masterMode?: string | null) {
  const out: Record<string, "major" | "minor"> = {};
  for (const [light, value] of Object.entries(lights)) {
    if (typeof value !== "string" || (light === "thr" && masterMode === "NAV")) continue;
    if (value.startsWith("major") || (light === "hit" && value.startsWith("minor"))) out[light] = "major";
    else if (value.startsWith("minor")) out[light] = "minor";
  }
  return out;
}

/** What a header shows from these lit lights: the warnings and cautions it's set to show. */
export function chosen(lit: Record<string, "major" | "minor">, p: AlertPick): { warning: string[]; caution: string[] } {
  const order = (a: string, b: string) => LIGHTS.indexOf(a as never) - LIGHTS.indexOf(b as never);
  const of = (level: "major" | "minor", allowed: string[]) =>
    Object.entries(lit)
      .filter(([k, l]) => l === level && allowed.includes(k))
      .map(([k]) => k)
      .sort(order);
  return { warning: of("major", p.warning), caution: of("minor", p.caution) };
}
