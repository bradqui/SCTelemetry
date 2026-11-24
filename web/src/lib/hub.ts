/** The hub's fleet page, signed in: the agent asks the hub for a one-time link (POST
 * /api/fleet/open on 127.0.0.1). For phones and other screens, your account, and admin;
 * the cockpit page shows the fleet itself too. In the Windows app (pywebview) the link
 * opens in the default browser; in a browser, in a new tab. */
declare global {
  interface Window {
    pywebview?: { api?: { open_external?: (url: string) => Promise<boolean> } };
  }
}

export async function openOnHub(): Promise<void> {
  const app = window.pywebview?.api?.open_external;
  if (app) {
    const body = await fetch("/api/fleet/open", { method: "POST" })
      .then((r) => r.json())
      .catch(() => ({}));
    if (body.url) await app(body.url);
    return;
  }
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
