# Joining a fleet

A **fleet** is your org's group on its own **hub**, a small server one of your admins runs ([Running a hub](/hub/running)). Join it, and everyone in the fleet sees everyone: who's flying what, where, in which mode, with which warnings.

## With your invite link

Your admin sends you an invite link, like `https://fleet.example.org/join/AbC…`.

1. In Starglance, open **Settings → Agent → Fleet**.
2. Paste the invite link, and pick your display name (your in-game handle by default).
3. That's it: your account is made and this PC is linked. Starglance starts sending.

![An invite page](/shots/app/hub-join.jpg)

Or from a terminal: `starglance link <invite link>`. Opening the link in a browser instead lets you join to watch, without a PC (you can link one later).

## What you share

Each fleet only gets what you share with it. Everything is on by default; switch off anything you'd rather keep to yourself under **Settings → Agent → What you share**. Anything switched off never leaves your PC.

| Category | What it covers |
|---|---|
| **Status** | in game, on foot or seated, your seat, your in-game handle |
| **Ship** | ship, mode, warning lights, fuel, flight data |
| **Weapons** | guns ready, countermeasures |
| **Vitals** | health, oxygen, food and water, injuries |
| **aUEC** | aUEC balance and contract rewards |
| **Location** | zone, jurisdiction, server, star system, quantum destination, ship you're aboard |
| **Contracts** | current contracts and objectives |
| **Combat** | kills, ships lost, session counts |

Never sent: world coordinates, chat, party channels, anything outside the game's telemetry and log.

::: warning Whoever runs your hub sees what you share
That's the point of a fleet, but it means you should only join hubs run by people you trust. See [Privacy](/privacy).
:::

## More than one fleet

Play with more than one org? **Join another fleet** with the other org's invite. Starglance sends to each, with its own **What you share**. The Fleet view and the Wingmates panel have a picker for which fleet to show.

Each fleet has a switch: off pauses sending to it without leaving. **Leave** (or `starglance unlink`) stops sending and makes the hub forget this PC.

## Another PC, or your phone

- **Another gaming PC**: run `starglance link https://your-hub-address` on it, then confirm the code it shows on the fleet page.
- **A phone or another browser**: on the fleet page, **Your account → Sign in on another device** shows a short code. On the phone, open the hub's address, choose **I have a code** and type it.
- **Discord**: if your hub offers it, **Sign in with Discord** works on any device once you've connected Discord under **Your account**.

## Your account

**Your account** on the hub's fleet page (your name, top right) has your display name, your linked PCs, the browsers signed in as you, the problem reports you sent, and **Delete my account**, which unlinks your PCs and removes your history from the fleet.

![Your account](/shots/app/hub-account.jpg)
