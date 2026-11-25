# Know before you use it

Starglance is a fan-made tool built on data the game doesn't promise to keep. We make a best effort to keep up with the game and fix things as we learn more, but some of what you see is a good guess, and any patch can change it.

## The game can change under it

- **The telemetry stream is an undocumented game feature.** It's off unless switched on in the game's `user.cfg`, and CIG can change, rename or remove it in any patch. Starglance re-reads the stream's layout whenever the game's exe changes and treats every field as optional, so a change should leave gaps rather than crash it. Gaps can still last until we update.
- **`Game.log` isn't an interface either.** Location, contracts, kills and losses, quantum routes and who's aboard which ship come from its text lines, and CIG can reword them at any time. When that happens, those parts go quiet until Starglance learns the new wording.

## What the game doesn't send today

As of Star Citizen LIVE, November 2026:

- **Hull health, shield levels and the master mode (NAV/SCM) aren't in the stream.** NAV/SCM is worked out from the quantum drive light and shield power. Hull and shields show the warning lights and power state, not percentages.
- **The COOL light is never lit by the game,** so Starglance shows it from whether the coolers have power.
- **Seat events are unreliable.** Seating is worked out from the state instead. Ship data arrives about 5 seconds after you sit down, after the animation.

## What's inferred, and can be wrong

- **Quantum travel is the biggest guess.** The game sends no "in quantum" signal at all, so Starglance works it out from three things together: the THR warning light coming on, the quantum drive being lit (NAV mode), and the speed and G-force freezing while you travel. The jump ends when the light clears, G-force comes back or the speed starts moving again. So:
  - a jump can start or end a moment late on the dashboard;
  - each leg of a multi-leg route counts as its own jump;
  - ships that don't send the THR light fall back to a rougher rule, which can mistake sitting still with a route plotted for a jump, or miss a leg;
  - the destination comes from `Game.log`'s route lines, so if their wording changes, jumps still show but the destination goes blank.
- **Who's aboard a ship** comes from its comms channel. The game doesn't always log leaving one, so you can show as aboard a ship you've left until something else ends it: another channel, a server change, death or a new game.
- **On foot and EVA** flicker around airlocks; Starglance smooths that over, so changes can show up a moment late.

## Other things to know

- **Don't fly by it.** It's a second screen, not a replacement for the game's own HUD, and it can lag or be wrong.
- **Not endorsed by CIG.** It only uses what the game offers on your PC: no game memory, no Easy Anti-Cheat, nothing sent to the game. CIG hasn't approved it, though, so using it is your call. The software comes as is, without warranty (MIT license).
- **In a fleet, whoever runs your org's hub sees everything you share** ([Privacy](/privacy)). Everyone else sees only what you share, while you're online.

Seen it get something wrong? [Report it](/guide/problem-reports): a report with the minutes around it is the fastest way to get it fixed. What the game sends, field by field, is in [FIELDS.md](https://github.com/bradqui/starglance/blob/main/docs/FIELDS.md).
