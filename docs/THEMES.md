# Manufacturer themes

The page (cockpit view and fleet page) is themed after Star Citizen's ship makers. A theme sets colours, typefaces, corners, borders, label style and a few small details that make the brand recognisable. The player picks dark or light; everything else comes from the manufacturer.

Settings (Customize → Theme, saved per browser):

- **Scheme**: dark or light.
- **Match the ship I'm in**: the theme follows the maker of the vehicle you're in, from the vehicle class prefix (`DRAK_Cutlass_Black` → Drake; `VNCL_*` → Esperia, `XIAN_*`/`XNAA_*` → Aopoa). Out of a vehicle, or with matching off, your default applies.
- **Default theme** (on foot): any of the 16.

On the fleet page your default themes the page; with matching on, the member you open is shown in their own ship's theme.

`?theme=DRAK&scheme=light` in the address previews a theme without saving it (handy for screenshots).

## How it works

Everything lives in [web/src/lib/themes.ts](../web/src/lib/themes.ts): the 16 themes and `applyTheme(element, theme, scheme)`, which sets CSS custom properties on the page (or on one member's panel) and `data-deco` for the details. Components only ever read tokens:

| Token | What |
|---|---|
| `--bg --bg-2 --panel --panel-2 --line --line-2` | surfaces and lines |
| `--text --text-2 --text-3` | text, strongest to faintest |
| `--accent --accent-2` | the brand colour and a second one for details (never status) |
| `--good --warn --bad --nav` | status colours and NAV/quantum. They keep their meaning in every theme; where a brand's accent sits near one, the status shifts hue (Drake: caution goes orange) |
| `--font --font-display --mono` | body, display (ship names, big numbers, titles: the `.display` class) and numbers |
| `--display-weight --display-style --display-spacing` | how the display face is set |
| `--label-case --label-spacing --label-style` | small labels: capitals or sentence case, tracking, italic |
| `--radius` | panels |
| `--radius-chip` | chips and badges (may be a pill) |
| `--radius-sm` | tiles: warning lights, readouts, buttons. The chip corner, capped at 10px for pill brands, so a square tile never becomes a circle its label can't fit |
| `--border-w --stripe --stripe-2 --shadow` | border width, hazard/safety stripes, soft shadows |

Details (`data-deco`, rules at the end of [web/src/app.css](../web/src/app.css)): `brackets` and `notch` (Aegis), `circle` (Anvil), `airy` (Origin, Crusader), `rule` (RSI), `hazard` (Drake), `tab` (MISC), `bars` (Argo), `speed` (Mirai), `hairline` (Kruger), `glyph` (Esperia), `hex` and `glow` (Aopoa), `facet` and `glow` (Gatac), `stitch` (Banu), `stripe` (Greycat), `rivets` (Tumbril), `pill` (Consolidated Outland).

Typefaces are bundled (Fontsource packages, latin subset only) and loaded per theme on first use, so the cockpit view works offline and a theme you never use costs nothing.

Rules for new or changed UI: no literal colours (use tokens, or `color-mix()` of tokens), corners from the three radius tokens, small labels with the `.label` class, ship names and big numbers with `.display`.

## What each theme is based on

The lore gives little visual detail, so most of each palette is design interpretation. Where we have real evidence it wins:

| Theme | Evidence |
|---|---|
| Argo | Documented: "industrial aesthetic with an orange and black livery", "orange user interfaces", cockpit views "divided by metal support bars" |
| Kruger | Seen in game: the L-21 Wolf's screens (added in 4.3, after the 3.24.2 screen rework) are rounded black panels with mint-green bars, white text and pill warning lights. Livery: "silver and white … replaced the red and yellow" |
| Gatac | Seen in game: the Syulen's holographic screens are violet with white type over a deep teal cabin |
| Aegis, Anvil, Drake | Have their own in-game screen styles since 3.24.2, not yet seen in a picture. Aegis's 2021 Gladius screens were cyan on black |
| Origin, RSI, Crusader, MISC, Consolidated Outland, Mirai, Esperia, Aopoa, Banu, Greycat, Tumbril | Interpretation of the lore (luxury, heritage, airliner, Japanese industrial, startup, racing, alien replicas, Xi'an, guild-built, work-site, desert military) |

The interactive mockups with design notes per brand were made before building this; screenshots of the in-game screens from inside each ship are the best way to tune the rest (pilot seat, PrintScreen or F12).

Sources: [Star Citizen Wiki: Ship manufacturers](https://starcitizen.tools/Ship_manufacturers) and each maker's page; [Origin Jumpworks](https://starcitizen.tools/Origin_Jumpworks); [Writer's Guide, Part Four](https://starcitizen.tools/Comm-Link:Writer%27s_Guide_-_Part_Four); [Alpha 3.24.2 patch notes](https://starcitizen.tools/Update:Star_Citizen_Alpha_3.24.2) ("manufacturer styles"); cockpit images on the wiki pages for the [L-21 Wolf](https://starcitizen.tools/L-21_Wolf), [Syulen](https://starcitizen.tools/Syulen) and [Gladius](https://starcitizen.tools/Gladius). Colours, typefaces and details beyond quoted phrases are this project's choices, not CIG's brand guides.
