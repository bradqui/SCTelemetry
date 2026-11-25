# Customizing

Open **Settings** with the sliders button at the top right. The **Dashboard** tab is about how things look; it's saved in this browser or window, so a tablet can look different from your PC. The **Agent** tab is about the app itself ([Getting started](/guide/getting-started#_3-switch-on-the-game-s-telemetry), [Joining a fleet](/fleet/joining)).

<Demo at="cruise" query="customize">Try it in the live demo</Demo>

![Settings, Dashboard tab, over the cockpit view](/shots/cockpit-customize.jpg)

## Themes

Starglance's own **Deep Space** look (ink blue, ice cyan and amber) is the default. Then seventeen themes, one per ship maker: their colours, typefaces, corners and the details that make each brand recognisable, like Drake's hazard stripes or Argo's metal frame.

<Clip name="clip-themes" caption="Switching themes: Drake, Anvil, Aegis, MISC, Origin." />

- **Scheme**: dark or light. Everything else comes from the maker.
- **Match the ship I'm in**: takes on the maker of whatever you board, and goes back to your own theme when you get out. Your own theme is then the one used *on foot*.

<div class="shots">
  <figure><img src="/shots/theme-anvil.jpg" alt="Anvil theme"><figcaption>Anvil</figcaption></figure>
  <figure><img src="/shots/theme-aegis.jpg" alt="Aegis theme"><figcaption>Aegis</figcaption></figure>
  <figure><img src="/shots/theme-misc.jpg" alt="MISC theme"><figcaption>MISC</figcaption></figure>
  <figure><img src="/shots/theme-light.jpg" alt="Origin theme, light"><figcaption>Origin, light</figcaption></figure>
</div>

Kruger and Gatac follow their in-game screens and Argo its documented orange UI. The rest interpret the lore; they'll be tuned as we collect screenshots of each maker's screens in game.

## Layouts and panels

- **Layouts**: pick Pilot, Combat, Explorer or Minimal to start from (or VR overlay and VR minimal in Compact).
- **Panels**: show or hide each one, and set its width (¼, ⅓, ½, ⅔ or full).
- **Move** a panel by dragging it on the dashboard while Settings is open.

## Following the flight

**Settings → Flight phases → Follow the flight** lets the dashboard follow what you're doing (takeoff and landing, cruise, quantum, combat, on foot). Panels never move, so your eyes always know where things are; only the emphasis changes.

- **Spotlight** lights the panels that matter now and dims the rest: in combat, Hull & shields, Warnings, Weapons and Power; when landing, Flight, Warnings and Fuel.
- **Focus strip** adds one slim band at the top with that phase's numbers: height above ground, climb rate and gear when landing; shields, warnings, guns and decoys in combat.
- **Both**, or **Off** (the default).

The Focus strip takes about 45 px; everything else fits a 1080p screen as it is.

## Look

- **HUD effects**: glow, scanlines and animations.
- **Hide ship panels on foot**: otherwise they wait on standby.
- **Keep the screen awake**: for a phone or tablet beside the game, while the page is open. It needs the hub's https page or this PC; on iPhone and iPad, iOS 18.4 or later.
- **Speed in** m/s or km/h.

## Activity

**Ships destroyed** chooses which ship losses the Activity panel and the fleet show:

- **Fleet**: ships fleet members destroy, and members' own ships lost.
- **Players**: also ships destroyed near a member where a player shot or lost one.
- **All**: every one the game logs nearby, NPCs too.

Nearby ones show small and grey.

## Header alerts

Which warning lights make the top bar flash *Warning* or *Caution*, for you and, on the fleet page, for the fleet. Turn off any you'd rather not be told about.

**Reset everything** at the bottom puts every dashboard setting back to how it started.

## Links that set the look

Handy for a shortcut or an overlay app:

| Add to the address | Does |
|---|---|
| `?compact=1` | the compact layout |
| `?theme=DRAK` | that theme, without saving it (`SG` for Deep Space, `AEGS`, `ANVL`, `ORIG`, `RSI`, `CRUS`, `DRAK`, `MISC`, `CNOU`, `ARGO`, `MRAI`, `KRIG`, `ESPR`, `AOPOA`, `GAMA`, `BANU`, `GRIN`, `TMBL`) |
| `?scheme=light` | light or dark, without saving it |
| `?customize` | opens Settings |
