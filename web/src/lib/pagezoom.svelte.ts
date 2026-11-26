// The page's zoom (Settings -> Look -> Size): one place for the cockpit, the hub's fleet
// page and the demos, so they all fill a big screen the same way (lib/scale).
import { autoScale, type Scale } from "./scale";

/** The zoom in use now, for Settings' hint. */
export const pageZoom = $state({ value: 1 });

/** Zoom the whole page by the size preference. Call it while a component initializes; it
 * follows the window's size and lets go when that component goes. Only the component that
 * owns the page calls it (the cockpit's App, the hub's FleetApp, the showcase). */
export function usePageZoom(get: () => { scale: Scale; compact?: boolean }): void {
  let w = $state(innerWidth);
  let h = $state(innerHeight);
  $effect(() => {
    const onResize = () => {
      w = innerWidth;
      h = innerHeight;
    };
    addEventListener("resize", onResize);
    return () => removeEventListener("resize", onResize);
  });
  const zoom = $derived.by(() => {
    const { scale, compact = false } = get();
    return scale === "auto" ? autoScale(w, h, compact) : scale;
  });
  $effect(() => {
    const root = document.documentElement.style;
    root.zoom = zoom === 1 ? "" : String(zoom);
    // Viewport units (vw, vh, dvh) zoom with the page: styles divide them by --z so a
    // full-height page stays one screen tall.
    if (zoom === 1) root.removeProperty("--z");
    else root.setProperty("--z", String(zoom));
    pageZoom.value = zoom;
  });
  $effect(() => () => {
    document.documentElement.style.zoom = "";
    document.documentElement.style.removeProperty("--z");
    pageZoom.value = 1;
  });
}
