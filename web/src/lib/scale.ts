// The dashboard's size on big screens. It's laid out for a 1920 x 1000 area (a 1080p
// screen less the window's edges); on a bigger one (1440p, 4K at 100 or 150% Windows
// scaling) Auto zooms the whole page evenly so it fills the screen the same way: every
// proportion the same, just larger. It never shrinks below 100% (smaller windows reflow
// instead), and Compact stays at 100% (a narrow column, sized by its own window).

export type Scale = "auto" | number;

/** The sizes Settings offers besides Auto. */
export const SCALES = [0.9, 1, 1.25, 1.5, 1.75, 2] as const;

const DESIGN_W = 1920;
const DESIGN_H = 1000;
const MAX = 3;

/** The zoom Auto picks for a window of this size, in 5% steps (so it doesn't twitch). */
export function autoScale(width: number, height: number, compact: boolean): number {
  if (compact || width <= 0 || height <= 0) return 1;
  const fit = Math.min(width / DESIGN_W, height / DESIGN_H);
  return fit < 1.05 ? 1 : Math.min(Math.floor(fit * 20) / 20, MAX);
}

export function readScale(raw: unknown): Scale {
  return typeof raw === "number" && (SCALES as readonly number[]).includes(raw) ? raw : "auto";
}

/** How much this element is zoomed: its on-screen width over its layout width. Pointer
 * coordinates and getBoundingClientRect are on-screen; style lengths are layout. */
export function zoomOf(el: Element): number {
  const w = (el as HTMLElement).offsetWidth;
  return w ? el.getBoundingClientRect().width / w || 1 : 1;
}
