/** Is this page on another device (Show on other devices: the agent's view-only server on
 * your network) rather than the PC itself? Then the PC-only controls are hidden: Agent
 * settings, joining a fleet, opening the hub's page. The agent's hello says for certain;
 * until it arrives, the address is a good guess (the PC's own page is on 127.0.0.1). */
export const view = $state({
  remote: !["127.0.0.1", "localhost", "[::1]"].includes(location.hostname),
});

/** A device the PC removed: its key no longer works, so back to the pairing page. */
export async function checkPaired(): Promise<void> {
  if (!view.remote) return;
  try {
    const r = await fetch("/api/mode", { cache: "no-store" });
    if (r.status === 401) location.assign("/pair");
  } catch {
    /* the PC is off or unreachable: keep trying to reconnect */
  }
}
