// Manufacturer themes: colours, typefaces, corners, labels and the small details that make
// each ship maker recognisable. The player picks dark or light; everything else comes from
// the manufacturer. Design notes and sources: docs/THEMES.md.
//
// A theme is applied as CSS custom properties on an element (the page, or one member's
// panel on the fleet page), so every component reads it through var(--...). Status
// colours keep their meaning everywhere; where a brand's accent sits near one of them,
// that status shifts hue instead of the brand.

export type Scheme = "dark" | "light";

export interface Palette {
  bg: string;
  bg2: string;
  panel: string;
  panel2: string;
  line: string;
  line2: string;
  text: string;
  text2: string;
  text3: string;
  accent: string;
  /** A second brand colour: details and decorations, never status. */
  accent2: string;
  good?: string;
  warn?: string;
  bad?: string;
  /** NAV mode and quantum travel. */
  nav?: string;
  /** Hazard and safety stripes. */
  stripe?: string;
  stripe2?: string;
}

export interface Theme {
  id: string;
  name: string;
  short: string;
  /** One line for the picker. */
  tagline: string;
  fonts: { display: string; body: string; mono: string };
  /** Loads this theme's typefaces (bundled, latin subset). */
  load: () => Promise<unknown>;
  displayWeight: number;
  displayStyle?: "italic";
  displaySpacing: string;
  labelCase: "uppercase" | "none";
  labelSpacing: string;
  labelStyle?: "italic";
  /** Panels. */
  radius: string;
  /** Chips and badges: may be a pill (999px). */
  radiusChip: string;
  border: string;
  /** Space-separated details: see the [data-deco] rules in app.css. */
  deco: string;
  /** The scheme the brand looks most at home in (both are always available). */
  home?: Scheme;
  dark: Palette;
  light: Palette;
}

const STATUS: Record<Scheme, Required<Pick<Palette, "good" | "warn" | "bad" | "nav">> & { shadow: string }> = {
  dark: { good: "#3ddc97", warn: "#ffb020", bad: "#ff4d5e", nav: "#a78bfa", shadow: "rgb(0 0 0 / 0.5)" },
  light: { good: "#13925c", warn: "#a86600", bad: "#cf2c3e", nav: "#6b4fd1", shadow: "rgb(20 30 40 / 0.14)" },
};

const all = (...loads: Promise<unknown>[]) => Promise.all(loads);

export const THEMES: Theme[] = [
  {
    // Starglance's own look, not a ship maker's: the default, and what you wear on foot
    // when your theme follows the ship you're in.
    id: "SG",
    name: "Starglance Deep Space",
    short: "Starglance",
    tagline: "Our own: ink blue, ice cyan, amber",
    fonts: { display: "Chakra Petch", body: "IBM Plex Sans", mono: "IBM Plex Mono" },
    load: () =>
      all(
        import("@fontsource/chakra-petch/latin-500.css"),
        import("@fontsource/chakra-petch/latin-600.css"),
        import("@fontsource/chakra-petch/latin-700.css"),
        import("@fontsource/ibm-plex-sans/latin-400.css"),
        import("@fontsource/ibm-plex-sans/latin-500.css"),
        import("@fontsource/ibm-plex-sans/latin-600.css"),
        import("@fontsource/ibm-plex-mono/latin-400.css"),
        import("@fontsource/ibm-plex-mono/latin-500.css"),
      ),
    displayWeight: 600,
    displaySpacing: "0.03em",
    labelCase: "uppercase",
    labelSpacing: "0.16em",
    radius: "10px",
    radiusChip: "5px",
    border: "1px",
    deco: "",
    dark: { bg: "#090c11", bg2: "#0e131a", panel: "#121922", panel2: "#17202b", line: "#222d3a", line2: "#34424f", text: "#e7edf3", text2: "#a2afbd", text3: "#6a7888", accent: "#5fd4e8", accent2: "#f0b45c" },
    light: { bg: "#eef2f6", bg2: "#e4eaf0", panel: "#f9fbfc", panel2: "#ffffff", line: "#d3dce5", line2: "#b5c3d0", text: "#0e151d", text2: "#3e4c5a", text3: "#6c7b8a", accent: "#0b7f97", accent2: "#a8661a" },
  },
  {
    id: "AEGS",
    name: "Aegis Dynamics",
    short: "Aegis",
    tagline: "Military steel, stark",
    fonts: { display: "Saira Condensed", body: "Saira", mono: "Share Tech Mono" },
    load: () =>
      all(
        import("@fontsource/saira-condensed/latin-700.css"),
        import("@fontsource/saira/latin-400.css"),
        import("@fontsource/saira/latin-600.css"),
        import("@fontsource/share-tech-mono/latin-400.css"),
      ),
    displayWeight: 700,
    displaySpacing: "0.04em",
    labelCase: "uppercase",
    labelSpacing: "0.18em",
    radius: "0px",
    radiusChip: "0px",
    border: "1px",
    deco: "brackets notch",
    dark: { bg: "#0a0c0f", bg2: "#101318", panel: "#14181e", panel2: "#191e25", line: "#262d36", line2: "#39434f", text: "#e8ecf0", text2: "#a5aeb9", text3: "#6c7682", accent: "#dfe6ee", accent2: "#c8393f" },
    light: { bg: "#dfe3e8", bg2: "#e9ecf0", panel: "#f4f6f8", panel2: "#ffffff", line: "#c7ced6", line2: "#a9b3be", text: "#0f1318", text2: "#3c4652", text3: "#66717d", accent: "#1b2430", accent2: "#b3262c" },
  },
  {
    id: "ANVL",
    name: "Anvil Aerospace",
    short: "Anvil",
    tagline: "Frontline curves and circles",
    fonts: { display: "Exo 2", body: "Exo 2", mono: "JetBrains Mono" },
    load: () =>
      all(
        import("@fontsource/exo-2/latin-400.css"),
        import("@fontsource/exo-2/latin-600.css"),
        import("@fontsource/exo-2/latin-800.css"),
        import("@fontsource/jetbrains-mono/latin-400.css"),
        import("@fontsource/jetbrains-mono/latin-600.css"),
      ),
    displayWeight: 800,
    displaySpacing: "0.01em",
    labelCase: "uppercase",
    labelSpacing: "0.12em",
    radius: "12px",
    radiusChip: "999px",
    border: "1px",
    deco: "circle",
    dark: { bg: "#0d0f0b", bg2: "#13160f", panel: "#181c14", panel2: "#1e2319", line: "#2c3324", line2: "#3e4733", text: "#e9ecdf", text2: "#aeb59c", text3: "#767d66", accent: "#cdd65f", accent2: "#8f9a5a" },
    light: { bg: "#e6e7dc", bg2: "#eeefe6", panel: "#f6f6ef", panel2: "#fffff8", line: "#cfd1bf", line2: "#b0b39b", text: "#191c12", text2: "#474d39", text3: "#6d7360", accent: "#5f6b1c", accent2: "#7d8754" },
  },
  {
    id: "ORIG",
    name: "Origin Jumpworks",
    short: "Origin",
    tagline: "Luxury silver and ivory",
    fonts: { display: "Jost", body: "Jost", mono: "IBM Plex Mono" },
    load: () =>
      all(
        import("@fontsource/jost/latin-300.css"),
        import("@fontsource/jost/latin-400.css"),
        import("@fontsource/jost/latin-500.css"),
        import("@fontsource/ibm-plex-mono/latin-400.css"),
        import("@fontsource/ibm-plex-mono/latin-500.css"),
      ),
    displayWeight: 300,
    displaySpacing: "0.22em",
    labelCase: "uppercase",
    labelSpacing: "0.28em",
    radius: "14px",
    radiusChip: "8px",
    border: "1px",
    deco: "airy",
    home: "light",
    dark: { bg: "#0f1012", bg2: "#141518", panel: "#191a1d", panel2: "#1f2024", line: "#2b2c31", line2: "#3a3c42", text: "#f1efea", text2: "#b3afa6", text3: "#7b7870", accent: "#d8c29a", accent2: "#a7a9ad", good: "#63d6a5", warn: "#f0b860", bad: "#ff6b72" },
    light: { bg: "#f3f1ec", bg2: "#ebe8e1", panel: "#fbfaf7", panel2: "#ffffff", line: "#e2ded5", line2: "#cfc9bd", text: "#16171a", text2: "#4d4b46", text3: "#85817a", accent: "#8a6a35", accent2: "#6f7277", good: "#1f8f60", warn: "#a76a10", bad: "#c73a44" },
  },
  {
    id: "RSI",
    name: "Roberts Space Industries",
    short: "RSI",
    tagline: "The heritage navy and blue",
    fonts: { display: "Titillium Web", body: "Titillium Web", mono: "Roboto Mono" },
    load: () =>
      all(
        import("@fontsource/titillium-web/latin-400.css"),
        import("@fontsource/titillium-web/latin-600.css"),
        import("@fontsource/titillium-web/latin-700.css"),
        import("@fontsource/roboto-mono/latin-400.css"),
        import("@fontsource/roboto-mono/latin-500.css"),
      ),
    displayWeight: 700,
    displaySpacing: "0.01em",
    labelCase: "uppercase",
    labelSpacing: "0.12em",
    radius: "6px",
    radiusChip: "3px",
    border: "1px",
    deco: "rule",
    dark: { bg: "#070b10", bg2: "#0b1118", panel: "#0f1720", panel2: "#131d28", line: "#1e2b38", line2: "#2a3a4b", text: "#e6eef6", text2: "#9fb0c2", text3: "#66798d", accent: "#46d3ff", accent2: "#a78bfa" },
    light: { bg: "#e7edf3", bg2: "#dfe7ef", panel: "#f6f9fc", panel2: "#ffffff", line: "#cad6e2", line2: "#aebfd0", text: "#0b1520", text2: "#3b4f63", text3: "#687b8f", accent: "#0a78b8", accent2: "#6b4fd1" },
  },
  {
    id: "CRUS",
    name: "Crusader Industries",
    short: "Crusader",
    tagline: "Airliner calm above Orison",
    fonts: { display: "Manrope", body: "Manrope", mono: "IBM Plex Mono" },
    load: () =>
      all(
        import("@fontsource/manrope/latin-400.css"),
        import("@fontsource/manrope/latin-600.css"),
        import("@fontsource/manrope/latin-800.css"),
        import("@fontsource/ibm-plex-mono/latin-400.css"),
        import("@fontsource/ibm-plex-mono/latin-500.css"),
      ),
    displayWeight: 800,
    displaySpacing: "-0.01em",
    labelCase: "none",
    labelSpacing: "0.02em",
    radius: "10px",
    radiusChip: "6px",
    border: "1px",
    deco: "airy",
    home: "light",
    dark: { bg: "#081226", bg2: "#0c1830", panel: "#10203d", panel2: "#142749", line: "#213761", line2: "#2e4a7c", text: "#eef3ff", text2: "#a9bbdc", text3: "#7083a8", accent: "#7fb2ff", accent2: "#ffd9a8", good: "#4fe0a6", warn: "#ffbe45", bad: "#ff5c6c" },
    light: { bg: "#eef3fb", bg2: "#e3ebf7", panel: "#ffffff", panel2: "#ffffff", line: "#d7e1f0", line2: "#b9c8e0", text: "#0c1a33", text2: "#3d5175", text3: "#6d7f9e", accent: "#2356d8", accent2: "#c4762a" },
  },
  {
    id: "DRAK",
    name: "Drake Interplanetary",
    short: "Drake",
    tagline: "Scrappy hazard yellow",
    fonts: { display: "Saira Stencil One", body: "Barlow Condensed", mono: "Share Tech Mono" },
    load: () =>
      all(
        import("@fontsource/saira-stencil-one/latin-400.css"),
        import("@fontsource/barlow-condensed/latin-400.css"),
        import("@fontsource/barlow-condensed/latin-600.css"),
        import("@fontsource/barlow-condensed/latin-700.css"),
        import("@fontsource/share-tech-mono/latin-400.css"),
      ),
    displayWeight: 400,
    displaySpacing: "0.03em",
    labelCase: "uppercase",
    labelSpacing: "0.1em",
    radius: "0px",
    radiusChip: "0px",
    border: "2px",
    deco: "hazard",
    dark: { bg: "#0b0b0a", bg2: "#121210", panel: "#171714", panel2: "#1d1d19", line: "#2e2d27", line2: "#45433a", text: "#ecebe4", text2: "#b0ad9f", text3: "#77756a", accent: "#f2c230", accent2: "#2a2a24", warn: "#ff8a3d", stripe: "#f2c230", stripe2: "#141412" },
    light: { bg: "#e7e4d8", bg2: "#dedacb", panel: "#f2efe4", panel2: "#faf8f0", line: "#cfcab8", line2: "#aea893", text: "#1a1915", text2: "#4a4740", text3: "#75716a", accent: "#8a6a00", accent2: "#1a1915", warn: "#b25a12", stripe: "#e3b21b", stripe2: "#1a1915" },
  },
  {
    id: "MISC",
    name: "MISC",
    short: "MISC",
    tagline: "Japanese industrial, modular",
    fonts: { display: "Zen Kaku Gothic New", body: "Zen Kaku Gothic New", mono: "M PLUS 1 Code" },
    load: () =>
      all(
        import("@fontsource/zen-kaku-gothic-new/latin-400.css"),
        import("@fontsource/zen-kaku-gothic-new/latin-700.css"),
        import("@fontsource/m-plus-1-code/latin-400.css"),
        import("@fontsource/m-plus-1-code/latin-600.css"),
      ),
    displayWeight: 700,
    displaySpacing: "0.02em",
    labelCase: "uppercase",
    labelSpacing: "0.1em",
    radius: "3px",
    radiusChip: "2px",
    border: "1px",
    deco: "tab",
    dark: { bg: "#0c100e", bg2: "#111613", panel: "#151b18", panel2: "#1a211d", line: "#26302b", line2: "#36443d", text: "#e8eee9", text2: "#a6b5ac", text3: "#6e7d74", accent: "#5cc08a", accent2: "#e8dcc0", good: "#3fd3e8" },
    light: { bg: "#eceae3", bg2: "#e3e0d6", panel: "#f7f6f1", panel2: "#fffefa", line: "#d6d2c6", line2: "#b8b3a4", text: "#141a16", text2: "#435048", text3: "#6f7a72", accent: "#23794d", accent2: "#8a7a55", good: "#0b7f93" },
  },
  {
    id: "CNOU",
    name: "Consolidated Outland",
    short: "C.O.",
    tagline: "Startup lime, unconventional",
    fonts: { display: "Sora", body: "Sora", mono: "Space Mono" },
    load: () =>
      all(
        import("@fontsource/sora/latin-400.css"),
        import("@fontsource/sora/latin-600.css"),
        import("@fontsource/sora/latin-800.css"),
        import("@fontsource/space-mono/latin-400.css"),
        import("@fontsource/space-mono/latin-700.css"),
      ),
    displayWeight: 800,
    displaySpacing: "-0.02em",
    labelCase: "none",
    labelSpacing: "0.01em",
    radius: "18px",
    radiusChip: "999px",
    border: "1px",
    deco: "pill",
    dark: { bg: "#0c0d14", bg2: "#12131d", panel: "#171926", panel2: "#1d2030", line: "#2a2d42", line2: "#3b3f5a", text: "#f2f3fa", text2: "#b0b3cc", text3: "#757995", accent: "#c6f432", accent2: "#ff6fb5", good: "#2dd4bf" },
    light: { bg: "#f4f5f8", bg2: "#eceef4", panel: "#ffffff", panel2: "#ffffff", line: "#dfe1ea", line2: "#c5c8d6", text: "#111324", text2: "#474b66", text3: "#7a7e98", accent: "#4d7a00", accent2: "#c2185b", good: "#0f8f80" },
  },
  {
    id: "ARGO",
    name: "Argo Astronautics",
    short: "Argo",
    tagline: "Workhorse orange on black",
    fonts: { display: "Chakra Petch", body: "Chakra Petch", mono: "Share Tech Mono" },
    load: () =>
      all(
        import("@fontsource/chakra-petch/latin-400.css"),
        import("@fontsource/chakra-petch/latin-600.css"),
        import("@fontsource/chakra-petch/latin-700.css"),
        import("@fontsource/share-tech-mono/latin-400.css"),
      ),
    displayWeight: 700,
    displaySpacing: "0.02em",
    labelCase: "uppercase",
    labelSpacing: "0.14em",
    radius: "0px",
    radiusChip: "0px",
    border: "1px",
    deco: "bars",
    dark: { bg: "#0a0a0a", bg2: "#111111", panel: "#161616", panel2: "#1c1c1c", line: "#2c2c2c", line2: "#444444", text: "#f0ece6", text2: "#b5ada3", text3: "#7a736b", accent: "#ff7a1a", accent2: "#3a3a3a", warn: "#ffd23f", bad: "#ff4b4b" },
    light: { bg: "#e3e1de", bg2: "#d6d3cf", panel: "#f3f1ee", panel2: "#fbfaf8", line: "#cdc9c3", line2: "#a8a39c", text: "#141210", text2: "#4a4540", text3: "#77716a", accent: "#c4510a", accent2: "#8c8780", warn: "#9a7400" },
  },
  {
    id: "MRAI",
    name: "Mirai",
    short: "Mirai",
    tagline: "Racing livery, italic speed",
    fonts: { display: "Kanit", body: "Kanit", mono: "Azeret Mono" },
    load: () =>
      all(
        import("@fontsource/kanit/latin-400.css"),
        import("@fontsource/kanit/latin-600.css"),
        import("@fontsource/kanit/latin-600-italic.css"),
        import("@fontsource/kanit/latin-800-italic.css"),
        import("@fontsource/azeret-mono/latin-400.css"),
        import("@fontsource/azeret-mono/latin-600.css"),
      ),
    displayWeight: 800,
    displayStyle: "italic",
    displaySpacing: "0.01em",
    labelCase: "uppercase",
    labelSpacing: "0.08em",
    labelStyle: "italic",
    radius: "2px",
    radiusChip: "2px",
    border: "1px",
    deco: "speed",
    dark: { bg: "#08070d", bg2: "#0e0c16", panel: "#13101d", panel2: "#181424", line: "#2a2338", line2: "#3d3352", text: "#f4f0ff", text2: "#b9b0d1", text3: "#7c7393", accent: "#ff3d9a", accent2: "#2de2ff", bad: "#ff4a3d" },
    light: { bg: "#f3f1f8", bg2: "#e9e6f2", panel: "#ffffff", panel2: "#ffffff", line: "#e0dbec", line2: "#c6bfd8", text: "#140f22", text2: "#4b4363", text3: "#7d7595", accent: "#d4136f", accent2: "#0091a8", bad: "#c4301f" },
  },
  {
    id: "KRIG",
    name: "Kruger Intergalactic",
    short: "Kruger",
    tagline: "Retro-futurist precision",
    fonts: { display: "Michroma", body: "Red Hat Text", mono: "Red Hat Mono" },
    load: () =>
      all(
        import("@fontsource/michroma/latin-400.css"),
        import("@fontsource/red-hat-text/latin-400.css"),
        import("@fontsource/red-hat-text/latin-600.css"),
        import("@fontsource/red-hat-mono/latin-400.css"),
        import("@fontsource/red-hat-mono/latin-600.css"),
      ),
    displayWeight: 400,
    displaySpacing: "0.06em",
    labelCase: "uppercase",
    labelSpacing: "0.2em",
    radius: "8px",
    radiusChip: "999px",
    border: "1px",
    deco: "hairline",
    home: "light",
    dark: { bg: "#101215", bg2: "#15181c", panel: "#1a1d22", panel2: "#20242a", line: "#2e333a", line2: "#434a53", text: "#f0f2f5", text2: "#b4bac2", text3: "#7a818b", accent: "#7ddc8c", accent2: "#d13b3b", good: "#3fd3e8" },
    light: { bg: "#e9ebee", bg2: "#dfe2e6", panel: "#f8f9fa", panel2: "#ffffff", line: "#d5d9de", line2: "#b6bcc4", text: "#15191e", text2: "#474e57", text3: "#737a84", accent: "#1d7f45", accent2: "#b52a2a", good: "#0b7f93" },
  },
  {
    id: "ESPR",
    name: "Esperia",
    short: "Esperia",
    tagline: "Alien replicas, museum-true",
    fonts: { display: "Cinzel", body: "Jura", mono: "Jura" },
    load: () =>
      all(
        import("@fontsource/cinzel/latin-500.css"),
        import("@fontsource/cinzel/latin-700.css"),
        import("@fontsource/jura/latin-400.css"),
        import("@fontsource/jura/latin-600.css"),
      ),
    displayWeight: 700,
    displaySpacing: "0.06em",
    labelCase: "uppercase",
    labelSpacing: "0.2em",
    radius: "16px 2px 16px 2px",
    radiusChip: "8px 1px",
    border: "1px",
    deco: "glyph",
    dark: { bg: "#0f0a0c", bg2: "#150e11", panel: "#1a1216", panel2: "#21171c", line: "#33242b", line2: "#4a343e", text: "#f2ebe4", text2: "#c0b0a6", text3: "#85766e", accent: "#e8d6b0", accent2: "#9a7bd8", good: "#5ad6a0", warn: "#f0b050", bad: "#ff5a64" },
    light: { bg: "#efe9e1", bg2: "#e6ded4", panel: "#f8f4ee", panel2: "#fffcf7", line: "#ddd3c7", line2: "#c1b3a4", text: "#1d1418", text2: "#52434a", text3: "#85767c", accent: "#7a5a24", accent2: "#6a4bb0" },
  },
  {
    id: "AOPOA",
    name: "Aopoa",
    short: "Aopoa",
    tagline: "Xi'an jade, organic and luminous",
    fonts: { display: "Comfortaa", body: "Quicksand", mono: "Fira Code" },
    load: () =>
      all(
        import("@fontsource/comfortaa/latin-500.css"),
        import("@fontsource/comfortaa/latin-700.css"),
        import("@fontsource/quicksand/latin-500.css"),
        import("@fontsource/quicksand/latin-700.css"),
        import("@fontsource/fira-code/latin-400.css"),
        import("@fontsource/fira-code/latin-500.css"),
      ),
    displayWeight: 700,
    displaySpacing: "0.01em",
    labelCase: "none",
    labelSpacing: "0.04em",
    radius: "18px",
    radiusChip: "10px",
    border: "1px",
    deco: "hex glow",
    dark: { bg: "#070d12", bg2: "#0b141b", panel: "#0f1a23", panel2: "#13212c", line: "#1d3140", line2: "#2a4557", text: "#eaf6f7", text2: "#a5c4c9", text3: "#6b8a90", accent: "#5fe3c0", accent2: "#b39dff", good: "#a6e36a", warn: "#ffc061", bad: "#ff5c7a", nav: "#b39dff" },
    light: { bg: "#eef5f5", bg2: "#e3eeef", panel: "#fbfefe", panel2: "#ffffff", line: "#d3e3e5", line2: "#b3cbcf", text: "#0b1a1f", text2: "#3b5961", text3: "#6b878d", accent: "#0f7d67", accent2: "#6a4fcf", good: "#4d7c0f", nav: "#6a4fcf" },
  },
  {
    id: "GAMA",
    name: "Gatac Manufacture",
    short: "Gatac",
    tagline: "Xi'an violet holograms",
    fonts: { display: "Oxanium", body: "Jura", mono: "Fira Code" },
    load: () =>
      all(
        import("@fontsource/oxanium/latin-600.css"),
        import("@fontsource/oxanium/latin-700.css"),
        import("@fontsource/jura/latin-400.css"),
        import("@fontsource/jura/latin-600.css"),
        import("@fontsource/fira-code/latin-400.css"),
        import("@fontsource/fira-code/latin-500.css"),
      ),
    displayWeight: 700,
    displaySpacing: "0.03em",
    labelCase: "uppercase",
    labelSpacing: "0.14em",
    radius: "10px 0",
    radiusChip: "4px 0",
    border: "1px",
    deco: "facet glow",
    dark: { bg: "#060b12", bg2: "#0a121c", panel: "#0d1724", panel2: "#111d2d", line: "#1c2c40", line2: "#2a3f58", text: "#eef0ff", text2: "#aab4d6", text3: "#6d789c", accent: "#b77cff", accent2: "#5fd0d8", good: "#4fd49a", bad: "#ff5c7a", nav: "#5fd0d8" },
    light: { bg: "#eeeef7", bg2: "#e4e4f1", panel: "#fafaff", panel2: "#ffffff", line: "#dadaea", line2: "#bcbcd6", text: "#121226", text2: "#46466a", text3: "#76769a", accent: "#6b36c9", accent2: "#147f8a", nav: "#147f8a" },
  },
  {
    id: "BANU",
    name: "Banu",
    short: "Banu",
    tagline: "Guild-built brass, patched",
    fonts: { display: "Philosopher", body: "Philosopher", mono: "Courier Prime" },
    load: () =>
      all(
        import("@fontsource/philosopher/latin-400.css"),
        import("@fontsource/philosopher/latin-700.css"),
        import("@fontsource/courier-prime/latin-400.css"),
        import("@fontsource/courier-prime/latin-700.css"),
      ),
    displayWeight: 700,
    displaySpacing: "0.01em",
    labelCase: "none",
    labelSpacing: "0.04em",
    radius: "8px",
    radiusChip: "4px",
    border: "1px",
    deco: "stitch",
    dark: { bg: "#120d0a", bg2: "#18110d", panel: "#1e1611", panel2: "#251b15", line: "#3a2b20", line2: "#54402f", text: "#f3e9dd", text2: "#c6b29c", text3: "#8a7663", accent: "#d6a85a", accent2: "#b0475a", good: "#6fd49a", warn: "#ff8a3d", bad: "#ff4f5f" },
    light: { bg: "#f0e7db", bg2: "#e7dccd", panel: "#f9f3ea", panel2: "#fffaf2", line: "#dccdb9", line2: "#c0aa8e", text: "#1f150e", text2: "#574533", text3: "#87745f", accent: "#8a5f1c", accent2: "#8e2c3a", warn: "#b25a12" },
  },
  {
    id: "GRIN",
    name: "Greycat Industrial",
    short: "Greycat",
    tagline: "Work-site safety yellow",
    fonts: { display: "Barlow", body: "Barlow", mono: "Roboto Mono" },
    load: () =>
      all(
        import("@fontsource/barlow/latin-400.css"),
        import("@fontsource/barlow/latin-600.css"),
        import("@fontsource/barlow/latin-800.css"),
        import("@fontsource/roboto-mono/latin-400.css"),
        import("@fontsource/roboto-mono/latin-500.css"),
      ),
    displayWeight: 800,
    displaySpacing: "0",
    labelCase: "uppercase",
    labelSpacing: "0.1em",
    radius: "8px",
    radiusChip: "4px",
    border: "1px",
    deco: "stripe",
    home: "light",
    dark: { bg: "#111214", bg2: "#17181b", panel: "#1c1e21", panel2: "#222428", line: "#2f3237", line2: "#44484f", text: "#eef0f2", text2: "#b2b6bd", text3: "#787d85", accent: "#ffcf33", accent2: "#5b6470", warn: "#ff8a3d", stripe: "#ffcf33" },
    light: { bg: "#e4e6e8", bg2: "#d9dcdf", panel: "#f5f6f7", panel2: "#ffffff", line: "#cdd1d5", line2: "#a9afb6", text: "#121417", text2: "#42474e", text3: "#6f757d", accent: "#9a7300", accent2: "#2f3640", warn: "#b25a12", stripe: "#ffcf33" },
  },
  {
    id: "TMBL",
    name: "Tumbril Land Systems",
    short: "Tumbril",
    tagline: "Desert-ready ground forces",
    fonts: { display: "Teko", body: "Barlow Condensed", mono: "Share Tech Mono" },
    load: () =>
      all(
        import("@fontsource/teko/latin-500.css"),
        import("@fontsource/teko/latin-600.css"),
        import("@fontsource/barlow-condensed/latin-400.css"),
        import("@fontsource/barlow-condensed/latin-600.css"),
        import("@fontsource/share-tech-mono/latin-400.css"),
      ),
    displayWeight: 600,
    displaySpacing: "0.04em",
    labelCase: "uppercase",
    labelSpacing: "0.12em",
    radius: "2px",
    radiusChip: "2px",
    border: "1px",
    deco: "rivets",
    dark: { bg: "#0d0e0a", bg2: "#13140f", panel: "#181a13", panel2: "#1e2018", line: "#2d3024", line2: "#424634", text: "#ecebdf", text2: "#b6b39c", text3: "#7c7a67", accent: "#d6b77e", accent2: "#7c8a4a" },
    light: { bg: "#e7e2d3", bg2: "#ddd7c5", panel: "#f3efe3", panel2: "#faf7ee", line: "#d1cab5", line2: "#b2a98f", text: "#1a1a12", text2: "#4c4a3a", text3: "#78755f", accent: "#7a5c22", accent2: "#556032" },
  },
];

export const THEME_BY_ID: Record<string, Theme> = Object.fromEntries(THEMES.map((t) => [t.id, t]));
export const DEFAULT_THEME = "SG";

/** Class-name prefixes that aren't a theme id of their own. */
const ALIASES: Record<string, string> = { VNCL: "ESPR", XIAN: "AOPOA", XNAA: "AOPOA" };

/** The theme for a vehicle class ("DRAK_Cutlass_Black" -> Drake), if we have one. */
export function themeForShip(cls: string | null | undefined): Theme | null {
  if (!cls) return null;
  const prefix = cls.split("_")[0].toUpperCase();
  return THEME_BY_ID[ALIASES[prefix] ?? prefix] ?? null;
}

export function palette(theme: Theme, scheme: Scheme): Required<Palette> & { shadow: string } {
  const p = { ...STATUS[scheme], ...theme[scheme] };
  return { ...p, stripe: p.stripe ?? p.accent, stripe2: p.stripe2 ?? p.bg };
}

/** `?theme=DRAK&scheme=light` in the address: preview a theme without saving it. */
export function forcedTheme(): { theme: Theme | null; scheme: Scheme | null } {
  const q = new URLSearchParams(location.search);
  const id = (q.get("theme") ?? "").toUpperCase();
  const scheme = q.get("scheme");
  return {
    theme: THEME_BY_ID[id] ?? null,
    scheme: scheme === "light" || scheme === "dark" ? scheme : null,
  };
}

const loaded = new Set<string>();

/** Load the theme's typefaces once (they swap in when ready). */
export function loadFonts(theme: Theme): void {
  if (loaded.has(theme.id)) return;
  loaded.add(theme.id);
  theme.load().catch(() => loaded.delete(theme.id));
}

const mix = (color: string, pct: number) => `color-mix(in srgb, ${color} ${pct}%, transparent)`;

/** Set a theme's tokens on an element: the page (<html>) or one part of it. */
export function applyTheme(el: HTMLElement, theme: Theme, scheme: Scheme): void {
  loadFonts(theme);
  const p = palette(theme, scheme);
  const stack = (f: string, rest: string) => `"${f}", ${rest}`;
  const ui = 'system-ui, -apple-system, "Segoe UI", sans-serif';
  const vars: Record<string, string> = {
    "--bg": p.bg,
    "--bg-2": p.bg2,
    "--panel": p.panel,
    "--panel-2": p.panel2,
    "--line": p.line,
    "--line-2": p.line2,
    "--text": p.text,
    "--text-2": p.text2,
    "--text-3": p.text3,
    "--accent": p.accent,
    "--accent-2": p.accent2,
    "--accent-dim": mix(p.accent, 20),
    "--good": p.good,
    "--good-dim": mix(p.good, 15),
    "--warn": p.warn,
    "--warn-dim": mix(p.warn, 15),
    "--bad": p.bad,
    "--bad-dim": mix(p.bad, 17),
    "--nav": p.nav,
    "--scm": p.accent,
    "--stripe": p.stripe,
    "--stripe-2": p.stripe2,
    "--shadow": p.shadow,
    "--font": stack(theme.fonts.body, ui),
    "--font-display": stack(theme.fonts.display, stack(theme.fonts.body, ui)),
    "--mono": stack(theme.fonts.mono, "ui-monospace, Consolas, monospace"),
    "--display-weight": String(theme.displayWeight),
    "--display-style": theme.displayStyle ?? "normal",
    "--display-spacing": theme.displaySpacing,
    "--label-case": theme.labelCase,
    "--label-spacing": theme.labelSpacing,
    "--label-style": theme.labelStyle ?? "normal",
    "--radius": theme.radius,
    "--radius-chip": theme.radiusChip,
    // Tiles (warning lights, readouts) take the chip corner, but never a pill: a round
    // tile can't hold its label.
    "--radius-sm": theme.radiusChip === "999px" ? "10px" : theme.radiusChip,
    "--border-w": theme.border,
  };
  for (const [k, v] of Object.entries(vars)) el.style.setProperty(k, v);
  el.style.colorScheme = scheme;
  el.dataset.theme = theme.id;
  el.dataset.scheme = scheme;
  el.dataset.deco = theme.deco;
}
