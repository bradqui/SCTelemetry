import { COMPACT_PRESETS, PRESETS, repairLayout, type Layout } from "./panels";

export const ACCENTS = {
  ice: { name: "Ice", color: "#46d3ff" },
  azure: { name: "Azure", color: "#6b8cff" },
  orchid: { name: "Orchid", color: "#e070ff" },
  silver: { name: "Silver", color: "#cfd8e3" },
} as const;
export type AccentId = keyof typeof ACCENTS;

export interface Prefs {
  accent: AccentId;
  /** Scanlines, glow and sweep animations. */
  effects: boolean;
  speedUnit: "ms" | "kmh";
  /** Hide ship panels when you're not in a ship. */
  autoHide: boolean;
  /** Master caution banner under the top bar. */
  caution: boolean;
  full: Layout;
  compact: Layout;
}

const KEY = "ft.prefs.v1";

export function defaultPrefs(): Prefs {
  return {
    accent: "ice",
    effects: true,
    speedUnit: "ms",
    autoHide: true,
    caution: true,
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
      accent: raw.accent in ACCENTS ? raw.accent : d.accent,
      effects: typeof raw.effects === "boolean" ? raw.effects : d.effects,
      speedUnit: raw.speedUnit === "kmh" ? "kmh" : "ms",
      autoHide: typeof raw.autoHide === "boolean" ? raw.autoHide : d.autoHide,
      caution: typeof raw.caution === "boolean" ? raw.caution : d.caution,
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
