import { mount } from "svelte";
import "../app.css";
import Showcase from "./Showcase.svelte";

export default mount(Showcase, { target: document.getElementById("app")! });
