# FAQ and troubleshooting

## It says "Waiting for Star Citizen"

- Is the game's telemetry switched on? **Settings → Agent → Game telemetry** should say **On** for the channel you play (LIVE, PTU…). If you just switched it on, restart the game: it reads the setting when it starts.
- Are you in the game? The stream starts once you've loaded in, not at the launcher or the main menu.
- Installed the game somewhere unusual? Run `starglance installs` to see what Starglance found. If it's missing, run `starglance status --path "D:\Games\StarCitizen"` (your StarCitizen folder) once: Starglance remembers the folder from then on.

## Ship panels are empty when I sit down

Ship data arrives about 5 seconds after you sit, once the animation finishes.

## Hull and shield percentages are missing

The game doesn't send them today. See [Know before you use it](/know-before#what-the-game-doesn-t-send-today).

## It showed a quantum jump that didn't happen (or missed one)

Quantum travel is worked out, not sent by the game, so it can be wrong. Please [report it](/guide/problem-reports): mark the moment with the flag or your hotkey, and send the report.

## Windows says it "protected your PC"

Starglance isn't code-signed. Choose **More info → Run anyway**. To check the file first, see [Checking a download](/guide/updates#checking-a-download).

## My antivirus flagged it

A false positive, common with Python programs packaged with PyInstaller. Check the file, then report it to your antivirus maker: [If your antivirus flags it](/guide/updates#if-your-antivirus-flags-it).

## Is it allowed? Can I get banned?

Starglance only uses what the game offers on your own PC: the telemetry stream the game provides once you switch it on, and its log file. It doesn't read game memory, doesn't touch Easy Anti-Cheat and never sends anything to the game. CIG hasn't endorsed it, though, so using it is your call.

## Does it slow the game down?

It's light: it runs at below-normal priority, and the game's data takes tens of microseconds a frame to process and store.

## Can my org see where I am?

Only what you share. **Location** covers your zone, jurisdiction, server, star system and quantum destination, never coordinates; switch it off under **What you share** if you'd rather not. See [Joining a fleet](/fleet/joining#what-you-share).

## The fleet page on my phone signed me out

Sign it in again with a code: **Your account → Sign in on another device** on a signed-in browser or in Starglance (**Fleet → Open on the hub**).

## Something else

Search the [issues](https://github.com/bradqui/starglance/issues), or open one. For a problem with what's on screen, a [problem report](/guide/problem-reports) helps the most.
