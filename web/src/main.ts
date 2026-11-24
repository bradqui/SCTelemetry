import { mount } from "svelte";
import "./app.css";
import App from "./App.svelte";
import FleetApp from "./components/fleet/FleetApp.svelte";
import type { HubMode } from "./lib/types";

// One page, two homes: the agent serves it on 127.0.0.1 (your own cockpit view),
// the hub serves it to the org (the fleet). /api/mode says which.
async function detectMode(): Promise<HubMode | null> {
  try {
    const r = await fetch("/api/mode", { cache: "no-store" });
    const body = await r.json();
    return body?.mode === "fleet" ? (body as HubMode) : null;
  } catch {
    return null; // an older agent without /api/mode: local
  }
}

const target = document.getElementById("app")!;
const hub = await detectMode();
export default hub ? mount(FleetApp, { target, props: { mode: hub } }) : mount(App, { target });
