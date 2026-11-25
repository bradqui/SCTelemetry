// Problem reports (docs/REPORTS.md): marking a moment and the agent's report calls. This
// PC only, except marking: a paired device (Show on other devices) can mark a moment, and
// the report is then made on the PC.
import { appWindow } from "./appwin.svelte";
import { view } from "./remote.svelte";

export async function reportCall<T = Record<string, unknown>>(path: string, body: unknown = {}): Promise<T> {
  const r = await fetch(`/api/agent/report/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error ?? `The agent said ${r.status}.`);
  return data as T;
}

/** Mark this moment (the top bar's flag). */
export async function markNow(): Promise<unknown> {
  if (!view.remote) return reportCall("mark");
  const r = await fetch("/api/mark", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error ?? `The PC said ${r.status}.`);
  return data;
}

/** Open the Report a problem dialog (App listens). */
export function openReport(): void {
  dispatchEvent(new CustomEvent("ft:report"));
}

/** A web page in the default browser (the app), or a new tab. */
export function openExternal(url: string): void {
  const app = appWindow.api?.open_external;
  if (app) void app(url);
  else window.open(url, "_blank", "noopener,noreferrer");
}
