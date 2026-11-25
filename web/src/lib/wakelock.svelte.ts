// Keep the screen on while the page is open (Customize → Keep the screen awake), for a
// phone or tablet propped up beside the game. The browser's Screen Wake Lock: it needs
// HTTPS (a hub's page; not "Show on other devices", which is plain http on your network),
// and on iPhone and iPad, iOS 18.4 or later for a page added to the Home Screen. The
// browser drops the lock whenever the page is hidden; it's asked for again on return,
// and on the next tap if it was refused (some browsers want a tap first).

interface Sentinel {
  release(): Promise<void>;
  addEventListener(type: "release", listener: () => void): void;
}

type Why = "off" | "on" | "unsupported" | "insecure" | "refused";

export const awake = $state<{ status: Why }>({ status: "off" });

let want = false;
let lock: Sentinel | null = null;
let asking = false;
let listening = false;

function api(): { request(type: "screen"): Promise<Sentinel> } | null {
  const n = typeof navigator === "undefined" ? null : (navigator as unknown as { wakeLock?: unknown });
  return (n?.wakeLock as { request(type: "screen"): Promise<Sentinel> } | undefined) ?? null;
}

/** Can this page keep the screen on at all? */
export function wakeSupport(): "ok" | "unsupported" | "insecure" {
  if (typeof window !== "undefined" && !window.isSecureContext) return "insecure";
  return api() ? "ok" : "unsupported";
}

async function grab(): Promise<void> {
  if (!want || lock || asking || document.visibilityState !== "visible") return;
  const wl = api();
  if (!wl) return;
  asking = true;
  try {
    const got = await wl.request("screen");
    if (!want) {
      void got.release();
      return;
    }
    lock = got;
    awake.status = "on";
    got.addEventListener("release", () => {
      if (lock === got) lock = null;
    });
  } catch {
    awake.status = "refused"; // low battery mode, or a tap is needed first
  } finally {
    asking = false;
  }
}

/** Switch keeping the screen on, from the preference. */
export function keepAwake(on: boolean): void {
  want = on;
  const support = wakeSupport();
  if (!on || support !== "ok") {
    awake.status = on && support !== "ok" ? support : "off";
    if (lock) {
      const l = lock;
      lock = null;
      void l.release().catch(() => {});
    }
    return;
  }
  if (!listening) {
    listening = true;
    document.addEventListener("visibilitychange", () => void grab());
    document.addEventListener("pointerdown", () => void grab(), { passive: true });
  }
  void grab();
}
