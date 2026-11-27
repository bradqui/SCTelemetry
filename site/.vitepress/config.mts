import { defineConfig } from "vitepress";

// The docs site, on GitHub Pages at https://bradqui.github.io/starglance/ (pages.yml).
// The live demos are built separately (npm run demo) into public/demo/.
const repo = "https://github.com/bradqui/starglance";
const site = "https://bradqui.github.io/starglance";

export default defineConfig({
  title: "Starglance",
  description: "Your Star Citizen ship and crew, at a glance: a cockpit dashboard and a fleet page, from the game's own telemetry.",
  base: "/starglance/",
  lang: "en-US",
  cleanUrls: true,
  lastUpdated: true,
  appearance: "dark",
  head: [
    ["link", { rel: "icon", type: "image/svg+xml", href: "/starglance/favicon.svg" }],
    ["meta", { property: "og:title", content: "Starglance" }],
    ["meta", { property: "og:description", content: "Your Star Citizen ship and crew, at a glance." }],
    ["meta", { property: "og:image", content: `${site}/shots/cockpit-pilot.jpg` }],
  ],
  // The demos are plain pages next to the docs, not VitePress pages.
  ignoreDeadLinks: [/^\/demo\//, /^\.\.?\/demo\//],
  themeConfig: {
    logo: { light: "/logo-light.svg", dark: "/logo.svg" },
    nav: [
      { text: "Guide", link: "/guide/getting-started", activeMatch: "/guide/" },
      { text: "Fleets", link: "/fleet/joining", activeMatch: "/fleet/" },
      { text: "Run a hub", link: "/hub/running", activeMatch: "/hub/" },
      {
        text: "Live demo",
        items: [
          { text: "Cockpit view", link: `${site}/demo/cockpit.html`, target: "_self" },
          { text: "Fleet page", link: `${site}/demo/`, target: "_self" },
        ],
      },
      { text: "Download", link: `${repo}/releases/latest` },
    ],
    sidebar: [
      {
        text: "Using Starglance",
        items: [
          { text: "Getting started", link: "/guide/getting-started" },
          { text: "The cockpit view", link: "/guide/cockpit" },
          { text: "Customizing", link: "/guide/customize" },
          { text: "Tablets, phones and VR", link: "/guide/other-devices" },
          { text: "Replaying recordings", link: "/guide/replay" },
          { text: "Reporting a problem", link: "/guide/problem-reports" },
          { text: "Updating and checking downloads", link: "/guide/updates" },
          { text: "Command line", link: "/guide/command-line" },
        ],
      },
      {
        text: "Fleets",
        items: [
          { text: "Joining a fleet", link: "/fleet/joining" },
          { text: "The fleet page", link: "/fleet/fleet-page" },
        ],
      },
      {
        text: "Running a hub",
        items: [
          { text: "Setting up a hub", link: "/hub/running" },
          { text: "Admin", link: "/hub/admin" },
        ],
      },
      {
        text: "About",
        items: [
          { text: "Know before you use it", link: "/know-before" },
          { text: "Privacy", link: "/privacy" },
          { text: "FAQ and troubleshooting", link: "/faq" },
        ],
      },
    ],
    socialLinks: [{ icon: "github", link: repo }],
    search: { provider: "local" },
    editLink: { pattern: `${repo}/edit/main/site/:path`, text: "Suggest a change to this page" },
    footer: {
      message:
        "Not affiliated with Cloud Imperium Games. Star Citizen is a trademark of Cloud Imperium Rights LLC. MIT licensed.",
    },
    outline: { level: [2, 3] },
  },
});
