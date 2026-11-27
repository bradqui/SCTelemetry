# Getting started

Starglance runs on the Windows PC you play on. It's one file, `starglance.exe`, with nothing to install.

::: tip Joining your org's fleet?
Start with the link your org gave you (an invite, or its hub's address): open it in your browser on this PC and sign in. The page walks you through downloading Starglance and linking it, and Starglance can switch on the game's telemetry in the same step. See [Joining a fleet](/fleet/joining).
:::

## 1. Download it

Download **starglance.exe** from the [latest release](https://github.com/bradqui/starglance/releases/latest) and put it wherever you like, for example in a `Starglance` folder in Documents.

::: info Windows may warn you the first time
Starglance isn't code-signed (a certificate costs money every year), so the first time you run it Windows SmartScreen may say it "protected your PC". Choose **More info → Run anyway**. Updates Starglance installs itself don't show this. To check the file first, see [Checking a download](/guide/updates#checking-a-download).
:::

## 2. Start it

Double-click it. Starglance opens in its own window, with an icon in the system tray:

- Closing the window keeps it running in the tray. Starting it again brings the window back.
- Right-click the tray icon for **Fleet**, **Settings**, **Always on top**, **Hide the title bar**, **Start with Windows**, **Mark this moment**, **Report a problem** and **Quit**.
- With the title bar hidden, drag the window by its top bar; minimize, maximize and close move there.
- The same view is at `http://127.0.0.1:8740` in any browser on this PC, for a second monitor or a [VR overlay](/guide/other-devices#vr-overlays).

Until the game is running, it says it's waiting for Star Citizen.

## 3. Switch on the game's telemetry

The game only offers its telemetry when a line in its `user.cfg` says so. Starglance can add it for you:

1. Open **Settings** (the sliders button, top right) → **Agent**.
2. Under **Game telemetry**, choose **Switch on** next to your install (LIVE, PTU, …).
3. Restart the game: it reads the setting when it starts.

<img src="/shots/app/agent-settings.jpg" alt="Settings, Agent tab: the fleet, what you share, and Game telemetry switched on for LIVE" style="max-width: 400px">

**Switch off** later puts `user.cfg` back exactly as it was.

## 4. Play

Load into the game. Within a few seconds of your character spawning, the cockpit view fills in. Ship data arrives about five seconds after you sit down in a seat, once the animation finishes.

![The cockpit view while flying](/shots/cockpit-pilot.jpg)

Next:

- [The cockpit view](/guide/cockpit): what everything on screen means.
- [Customizing](/guide/customize): layouts, panels and themes.
- [Joining a fleet](/fleet/joining): if your org runs a hub.

::: tip Starting with Windows
**Settings → Agent → Window → Start with Windows** (or the tray menu) starts Starglance in the tray when you sign in, so it's ready before the game is.
:::
