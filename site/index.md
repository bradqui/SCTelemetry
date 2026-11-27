---
layout: home
title: Starglance
titleTemplate: Your Star Citizen ship and crew, at a glance

hero:
  name: Starglance
  text: Your ship and crew, at a glance
  tagline: A cockpit dashboard for your second screen, tablet or VR overlay, and a live fleet page for your org. Built from Star Citizen's own telemetry. Free and open source.
  image:
    light: /logo-light.svg
    dark: /logo.svg
    alt: Starglance
  actions:
    - theme: brand
      text: Get started
      link: /guide/getting-started
    - theme: alt
      text: Try the live demo
      link: https://www.starglance.app/demo/cockpit.html
      target: _self
    - theme: alt
      text: Download
      link: https://github.com/bradqui/starglance/releases/latest

features:
  - icon: 🛩️
    title: Your cockpit, on another screen
    details: Flight, heading, warnings, fuel, power, weapons, vitals, location and your contract, live, on a second monitor, a tablet or a VR overlay.
    link: /guide/cockpit
    linkText: The cockpit view
  - icon: 🛰️
    title: Your whole fleet
    details: Who's flying what, who's aboard whose ship, in which mode, where, with which warnings. Anyone's full dashboard is a click away, on a PC or a phone.
    link: /fleet/fleet-page
    linkText: The fleet page
  - icon: 🎨
    title: Seventeen ship-maker themes
    details: Drake, Anvil, Origin, Aegis and thirteen more, dark or light. It can switch to the maker of whatever you board.
    link: /guide/customize
    linkText: Customizing
  - icon: 🔒
    title: Only what the game offers
    details: Reads the game's local telemetry stream and its Game.log. No game memory, nothing near Easy Anti-Cheat, nothing sent to the game. You choose what your fleet sees.
    link: /privacy
    linkText: Privacy
  - icon: 🖥️
    title: Your org runs its own hub
    details: One Docker container behind https, about ten minutes to set up. Invites, admin tools, the fleet page and an API for bots. No central service.
    link: /hub/running
    linkText: Running a hub
  - icon: 🐞
    title: Easy problem reports
    details: Flag a moment, even from inside the game with a hotkey. Starglance packs up those minutes, takes the names out, and you send it to your admins or a GitHub issue.
    link: /guide/problem-reports
    linkText: Reporting a problem
---

## See it

<Clip name="clip-replay" caption="The cockpit view on the way to a quantum jump to Bounty Beacon." />

<div class="shots">
  <figure><img src="/shots/fleet-cards.jpg" alt="The fleet page: everyone's ship, speed, altitude and fuel on cards, with the roster grouped by ship"><figcaption>The fleet page: everyone at a glance.</figcaption></figure>
  <figure><img src="/shots/theme-drake.jpg" alt="The cockpit view in the Drake theme, with hazard stripes"><figcaption>One of seventeen themes: Drake.</figcaption></figure>
</div>

Both views run live in your browser, on telemetry recorded in game: [the cockpit view](https://www.starglance.app/demo/cockpit.html) and [the fleet page](https://www.starglance.app/demo/).

::: warning A fan-made tool
Starglance isn't affiliated with or endorsed by Cloud Imperium Games. The game's telemetry is an undocumented feature that any patch can change. Read [Know before you use it](/know-before).
:::
