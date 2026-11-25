# The cockpit view

The cockpit view is your own dashboard. It shows what the game sends about your ship and your character, about 17 times a second, plus what Starglance reads from the game's `Game.log`.

<Demo at="cruise">Open the cockpit view, playing a recorded session</Demo>

![The cockpit view in the Pilot layout](/shots/cockpit-pilot.jpg)

## The top bar

![The top bar](/shots/cockpit-topbar.jpg)

From left to right:

- **Your ship** and its maker, and your **seat** (Pilot, Co-pilot, Turret…). On foot it says *On foot* or *EVA*, and which ship you're aboard if you're in someone's.
- **Where you are**: armistice zone, jurisdiction, monitored space, and the server you're on.
- **The master warning**, when any warning light is on: *Warning* for the red ones, *Caution* for the amber ones, with their names. It lives in the top bar so nothing else on screen moves when it fires.
- **The mode**: **NAV**, **SCM**, **QT** while in quantum travel, or *Powered down*.
- **Fleet**, when you're in a fleet: opens the fleet view in this window ([The fleet page](/fleet/fleet-page)).
- **Update**, when a new version is out ([Updating](/guide/updates)).
- **The flag**: marks this moment for a [problem report](/guide/problem-reports).
- **Live** (or **Replay** in a recording), **Compact** for the narrow layout, and the **sliders** button for Settings.

![A warning in the top bar](/shots/header-warning.jpg)

## The panels

Every panel can be shown, hidden, resized and moved ([Customizing](/guide/customize)). Ship panels wait on standby when you're on foot, or hide.

| Panel | What it shows |
|---|---|
| **Heading** | A compass tape with your heading. In deep space, where the game has no heading, it says so. |
| **Flight** | Speed dial with the mode, altitude and height above ground, vertical speed, G-force, atmosphere; flight assists (coupled, G-safe, cruise, proximity, boost); your quantum route and whether you've arrived. |
| **Hull & shields** | Your ship as an arrow inside a ring of four shield faces (front, sides, back): lit when shields are powered, dashed when they're down. The arrow takes the hull's colour, the engines glow when they're on, and dots show the landing gear. The game doesn't send hull or shield percentages today, so the bars beside it say so. |
| **Warnings** | The ten warning lights (power, weapons, thrusters, shields, cooling, quantum, radar, proximity, hit, missile), plus flying or landed and the gear. |
| **Trends** | Speed, altitude and G-force over the last three minutes. |
| **Fuel** | Hydrogen, quantum fuel and boost. |
| **Power** | Which of the ship's systems are powered. |
| **Weapons** | Each gun and whether it's ready, gimbals, and your decoys and noise countermeasures. |
| **Vitals** | Health, oxygen, hunger and thirst, heart rate, body temperature, and injuries. |
| **Environment** | Temperature, gravity, pressure and air outside. |
| **Contract** | Your current contracts, with the objective and the reward. |
| **Activity** | What just happened (seats, takeoff and landing, NAV and SCM, quantum jumps, warnings, kills, contracts, zones), with this session's counts and filters. |
| **Wingmates** | Your fleet next to your own dashboard: everyone's ship, mode, speed and altitude ([The fleet page](/fleet/fleet-page#wingmates)). |

On foot, the view is about you: vitals, environment, contract, activity.

![On foot](/shots/cockpit-on-foot.jpg)

## Layouts

Four layouts come built in, and you can change any of them:

- **Pilot**: everything, flight first.
- **Combat**: warnings, shields, weapons and activity up top.
- **Explorer**: environment, fuel and trends.
- **Minimal**: the few numbers that matter.

![The Combat layout](/shots/cockpit-combat.jpg)

**Compact** (top bar) switches to a narrow single column for VR overlays and side screens, with its own layouts: **VR overlay** and **VR minimal**. See [Tablets, phones and VR](/guide/other-devices).

## What it can't show

Some things the game doesn't send, and some Starglance works out for itself. The main ones:

- **Hull and shield levels** aren't in the stream, only their warning lights and power.
- **NAV and SCM** are worked out from the quantum drive's light and shield power.
- **Quantum travel** has no signal of its own; it's worked out from the THR light, the quantum drive and the speed freezing. A jump can start or end a moment late.

The full list is in [Know before you use it](/know-before).
