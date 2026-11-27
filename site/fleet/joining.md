# Joining a fleet

A **fleet** is your org's group on its own **hub**, a small server one of your admins runs ([Running a hub](/hub/running)). Join it, and everyone in the fleet sees everyone: who's flying what, where, in which mode, with which warnings.

## With your org's link

Your org gives you a link: an **invite** from an admin (like `https://fleet.example.org/join/AbC…`), or, if your org uses Discord, just **its hub's address**, where anyone with the org's member role signs in with Discord. Open it in your browser, on the PC you play on:

1. **Join**: with Discord, or by picking a display name (your in-game handle is a good choice).
2. The page takes you through setting up Starglance:
   - **Download** it ([Getting started](/guide/getting-started) has the details, including the Windows warning the first time);
   - **Open it**;
   - **Link this PC**. Your browser asks to open Starglance: allow it.
3. Starglance asks you to confirm: the fleet's name, its address and your name. Tick **Switch on the game's telemetry** if it's off, and choose **Join**. Restart the game if it's running.

That's it: the page shows your PC as linked, and Starglance sends to the fleet whenever it's running. **Skip for now** on that page lets you just watch the fleet from the browser, and you can set up a PC later at the hub's `/setup` page (or **Your account → Your PCs**).

<img src="/shots/app/hub-welcome.jpg" alt="After joining: download Starglance, open it, Link this PC" style="max-width: 480px">

<img src="/shots/app/link-this-pc.jpg" alt="Starglance asks before joining: the fleet, its address, your name, and a box to switch on the game's telemetry">

**Nothing happened when you clicked Link this PC?** Make sure Starglance is open, then click **Try again**. Your browser may also have blocked the prompt. Or skip the button: in Starglance, **Settings → Agent → Fleet → Or enter the hub's address here**, type the hub's address and confirm on the page that opens. That box takes an invite link too, and so does the command line: `starglance link <invite link>`.

## What you share

Each fleet only gets what you share with it. Everything is on by default; switch off anything you'd rather keep to yourself under **Settings → Agent → What you share**. Anything switched off never leaves your PC.

| Category | What it covers |
|---|---|
| **Status** | in game, on foot or seated, your seat, your in-game handle |
| **Ship** | ship, mode, warning lights, fuel, flight data |
| **Weapons** | guns ready, countermeasures |
| **Vitals** | health, oxygen, food and water, injuries |
| **aUEC** | aUEC balance and contract rewards |
| **Location** | zone, jurisdiction, server, star system, planet or moon, landing area, quantum destination, ship you're aboard |
| **Contracts** | current contracts and objectives |
| **Combat** | kills, ships lost, session counts |

Never sent: world coordinates, chat, party channels, anything outside the game's telemetry and log.

::: warning Whoever runs your hub sees what you share
That's the point of a fleet, but it means you should only join hubs run by people you trust. See [Privacy](/privacy).
:::

## More than one fleet

Play with more than one org? Open the other org's link the same way, or use **Join another fleet** in Starglance. Starglance sends to each, with its own **What you share**. The Fleet view and the Wingmates panel have a picker for which fleet to show.

Each fleet has a switch: off pauses sending to it without leaving. **Leave** (or `starglance unlink`) stops sending and makes the hub forget this PC.

## Another PC, or your phone

- **Another gaming PC**: open the hub's `/setup` page on it (for example `https://fleet.example.org/setup`), sign in, and follow the steps. Or run `starglance link https://your-hub-address` on it, then confirm the code it shows on the fleet page.
- **A phone or another browser**: on the fleet page, **Your account → Sign in on another device** shows a short code. On the phone, open the hub's address, choose **I have a code** and type it.
- **Discord**: if your hub offers it, **Sign in with Discord** works on any device once you've connected Discord under **Your account**.

## Your account

**Your account** on the hub's fleet page (your name, top right) has your display name, your linked PCs, the browsers signed in as you, the problem reports you sent, and **Delete my account**, which unlinks your PCs and removes your history from the fleet.

![Your account](/shots/app/hub-account.jpg)
