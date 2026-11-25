import { defaultAlerts, loadAlerts, type Alerts } from "./alerts";
import type { Destroyed } from "./format";
import type { Focus } from "./phase";
import { COMPACT_PRESETS, PRESETS, repairLayout, type Layout } from "./panels";
import { DEFAULT_THEME, THEME_BY_ID, type Scheme } from "./themes";

export interface Prefs {
  /** Dark or light; the manufacturer theme supplies everything else. */
  scheme: Scheme;
  /** Manufacturer theme when you're not in a vehicle (or when matching is off). */
  theme: string;
  /** Switch to the manufacturer of the vehicle you're in. */
  matchShip: boolean;
  /** Scanlines, glow and sweep animations. */
  effects: boolean;
  speedUnit: "ms" | "kmh";
  /** Hide ship panels when you're not in a ship. */
  autoHide: boolean;
  /** Which warning lights go in your top bar and the fleet header (lib/alerts.ts). */
  alerts: Alerts;
  /** Which ships destroyed show in Activity (lib/format destroyedShown). */
  destroyed: Destroyed;
  /** Ask the browser to keep the screen on while this page is open (lib/wakelock). */
  awake: boolean;
  /** Following the flight (lib/phase): Spotlight, the Focus strip, both, or off. */
  focus: Focus;
  full: Layout;
  compact: Layout;
}

const KEY = "ft.prefs.v1";

export function defaultPrefs(): Prefs {
  return {
    scheme: "dark",
    theme: DEFAULT_THEME,
    matchShip: true,
    effects: true,
    speedUnit: "ms",
    autoHide: true,
    alerts: defaultAlerts(),
    destroyed: "fleet",
    awake: false,
    focus: "off",
    full: structuredClone(PRESETS[0].layout),
    compact: structuredClone(COMPACT_PRESETS[0].layout),
  };
}

function load(): Prefs {
  const d = defaultPrefs();
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) ?? "null");
    if (!raw || typeof raw !== "object") return d;
    return {
      scheme: raw.scheme === "light" ? "light" : "dark",
      theme: typeof raw.theme === "string" && raw.theme in THEME_BY_ID ? raw.theme : d.theme,
      matchShip: typeof raw.matchShip === "boolean" ? raw.matchShip : d.matchShip,
      effects: typeof raw.effects === "boolean" ? raw.effects : d.effects,
      speedUnit: raw.speedUnit === "kmh" ? "kmh" : "ms",
      autoHide: typeof raw.autoHide === "boolean" ? raw.autoHide : d.autoHide,
      alerts: loadAlerts(raw.alerts, raw.caution),
      destroyed: ["none", "fleet", "players", "all"].includes(raw.destroyed) ? raw.destroyed : d.destroyed,
      awake: raw.awake === true,
      focus: ["spot", "strip", "both"].includes(raw.focus) ? raw.focus : "off",
      full: repairLayout(raw.full, d.full),
      compact: repairLayout(raw.compact, d.compact),
    };
  } catch {
    return d;
  }
}

/** Display preferences, saved in this browser. */
export class PrefsStore {
  value = $state<Prefs>(load());

  save(): void {
    try {
      localStorage.setItem(KEY, JSON.stringify(this.value));
    } catch {
      /* storage unavailable: preferences last until the page closes */
    }
  }

  reset(): void {
    this.value = defaultPrefs();
  }
}
