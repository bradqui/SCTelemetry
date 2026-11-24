/** The hub's fleet page in a new tab, signed in: the agent asks the hub for a one-time
 * link (POST /api/fleet/open on 127.0.0.1). For phones and other screens, your account,
 * and admin; the cockpit page shows the fleet itself too. */
export async function openOnHub(): Promise<void> {
  const tab = window.open("about:blank", "_blank");
  try {
    const r = await fetch("/api/fleet/open", { method: "POST" });
    const body = await r.json();
    if (body.url && tab) tab.location.href = body.url;
    else tab?.close();
  } catch {
    tab?.close();
  }
}
