// The dashboard's panels, the layouts people can arrange them into, and presets.

export const PANEL_IDS = [
  "heading",
  "flight",
  "ship",
  "warnings",
  "status",
  "trends",
  "fuel",
  "power",
  "weapons",
  "vitals",
  "environment",
  "mission",
  "events",
  "wingmates",
] as const;
export type PanelId = (typeof PANEL_IDS)[number];

export type Span = 3 | 4 | 6 | 8 | 12;
export const SPANS: { span: Span; label: string }[] = [
  { span: 3, label: "¼" },
  { span: 4, label: "⅓" },
  { span: 6, label: "½" },
  { span: 8, label: "⅔" },
  { span: 12, label: "Full" },
];

export interface PanelInfo {
  title: string;
  blurb: string;
  /** Only means something in a ship (can auto-hide on foot). */
  ship: boolean;
}

export const PANELS: Record<PanelId, PanelInfo> = {
  heading: { title: "Heading", blurb: "Compass tape", ship: true },
  flight: {
    title: "Flight",
    blurb: "Speed dial, altitude, climb, G; the compass and their history when those panels are off",
    ship: true,
  },
  ship: { title: "Hull & shields", blurb: "Ship diagram, hull and shield levels", ship: true },
  warnings: { title: "Warnings", blurb: "The ten warning lights, gear, landed", ship: true },
  status: { title: "Ship", blurb: "Hull, shields, power, gear and the ten warning lights", ship: true },
  trends: { title: "Trends", blurb: "Speed, altitude and G over the last 3 minutes", ship: true },
  fuel: { title: "Fuel", blurb: "Hydrogen, quantum fuel, boost", ship: true },
  power: { title: "Power", blurb: "Which ship systems are on", ship: true },
  weapons: { title: "Weapons", blurb: "Guns, gimbals, countermeasures", ship: true },
  vitals: { title: "Vitals", blurb: "Health, oxygen, hunger, thirst, heart rate", ship: false },
  environment: { title: "Environment", blurb: "Temperature, gravity, pressure, air", ship: false },
  mission: { title: "Contract", blurb: "Current contract, objective, rewards", ship: false },
  events: {
    title: "Activity",
    blurb: "What just happened, session counts, filters; your contract when that panel is off",
    ship: false,
  },
  wingmates: { title: "Wingmates", blurb: "Your fleet: ship, mode, speed, altitude (when linked)", ship: false },
};

export interface Slot {
  id: PanelId;
  span: Span;
  hidden?: boolean;
}

export type Layout = Slot[];

function layout(visible: [PanelId, Span][]): Layout {
  const shown = new Set(visible.map(([id]) => id));
  return [
    ...visible.map(([id, span]) => ({ id, span })),
    ...PANEL_IDS.filter((id) => !shown.has(id)).map((id) => ({ id, span: 4 as Span, hidden: true })),
  ];
}

export interface Preset {
  id: string;
  title: string;
  blurb: string;
  layout: Layout;
}

export const PRESETS: Preset[] = [
  {
    id: "pilot",
    title: "Pilot",
    blurb: "Everything, flight first",
    layout: layout([
      ["flight", 6],
      ["status", 6],
      ["fuel", 3],
      ["power", 3],
      ["weapons", 3],
      ["vitals", 3],
      ["events", 6],
      ["wingmates", 6],
    ]),
  },
  {
    id: "combat",
    title: "Combat",
    blurb: "Shields, warnings and guns up front",
    layout: layout([
      ["status", 6],
      ["flight", 6],
      ["weapons", 3],
      ["power", 3],
      ["fuel", 3],
      ["vitals", 3],
      ["events", 6],
      ["wingmates", 6],
    ]),
  },
  {
    id: "explorer",
    title: "Explorer",
    blurb: "Trends, environment and vitals",
    layout: layout([
      ["flight", 6],
      ["environment", 3],
      ["vitals", 3],
      ["events", 8],
      ["fuel", 4],
    ]),
  },
  {
    id: "minimal",
    title: "Minimal",
    blurb: "Just the essentials",
    layout: layout([
      ["flight", 8],
      ["status", 4],
    ]),
  },
];

export const COMPACT_PRESETS: Preset[] = [
  {
    id: "vr",
    title: "VR overlay",
    blurb: "Narrow, for OVR Toolkit or XSOverlay",
    layout: layout([
      ["flight", 12],
      ["status", 12],
      ["fuel", 6],
      ["weapons", 6],
      ["mission", 12],
      ["vitals", 12],
    ]),
  },
  {
    id: "vr-min",
    title: "VR minimal",
    blurb: "Flight and warnings only",
    layout: layout([
      ["flight", 12],
      ["warnings", 12],
    ]),
  },
];

/** Is this panel on screen in the layout in use (full or compact)? Panels use it to take
 * over a job when its own panel is off: Flight draws the compass and the history when the
 * Heading and Trends panels aren't shown; Activity shows the contract when Contract isn't. */
export function showing(prefs: { full: Layout; compact: Layout }, compact: boolean, id: PanelId): boolean {
  return (compact ? prefs.compact : prefs.full).some((s) => s.id === id && !s.hidden);
}

/** The built-in layouts before 0.10, by their visible panels: a saved layout still exactly
 * one of these (never customized) moves to that preset's new version. */
const OLD_PRESETS: Record<string, string> = {
  "heading:12,flight:6,ship:3,warnings:3,fuel:3,power:3,weapons:3,vitals:3,mission:3,events:6,trends:3,wingmates:6": "pilot",
  "ship:4,warnings:4,weapons:4,flight:6,power:3,fuel:3,events:6,mission:3,vitals:3,wingmates:6": "combat",
  "heading:12,flight:6,trends:6,environment:3,vitals:3,mission:3,events:3": "explorer",
  "flight:8,warnings:4,ship:6,fuel:6": "minimal",
  "heading:12,flight:12,warnings:12,ship:6,fuel:6,weapons:12,mission:12,vitals:12": "vr",
};

export function upgradeLayout(saved: Layout): Layout {
  const key = saved
    .filter((s) => !s.hidden)
    .map((s) => `${s.id}:${s.span}`)
    .join(",");
  const id = OLD_PRESETS[key];
  const preset = id ? [...PRESETS, ...COMPACT_PRESETS].find((p) => p.id === id) : undefined;
  return preset ? structuredClone(preset.layout) : saved;
}

/** A saved layout with any panels added since it was saved appended (hidden). */
export function repairLayout(saved: unknown, fallback: Layout): Layout {
  if (!Array.isArray(saved)) return structuredClone(fallback);
  const seen = new Set<PanelId>();
  const out: Layout = [];
  for (const s of saved) {
    if (!s || typeof s !== "object") continue;
    const { id, span, hidden } = s as Slot;
    if (!PANEL_IDS.includes(id) || seen.has(id)) continue;
    seen.add(id);
    out.push({ id, span: SPANS.some((x) => x.span === span) ? span : 4, hidden: hidden === true });
  }
  for (const id of PANEL_IDS) if (!seen.has(id)) out.push({ id, span: 4, hidden: true });
  return out;
}
