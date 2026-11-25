import { mount } from "svelte";
import "../app.css";
import CockpitDemo from "./CockpitDemo.svelte";

// The cockpit demo page (demo/cockpit.html): the real App on a recorded session.
export default mount(CockpitDemo, { target: document.getElementById("app")! });
