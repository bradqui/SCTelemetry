# Reporting a problem

Something looked wrong? Starglance keeps the last 30 minutes of what the game sent, on your PC only, so you can report it after the fact, with the data that shows what happened.

## 1. Mark the moment

Any of these marks it:

- the **flag** button in the top bar;
- **Mark this moment** in the tray menu;
- a **hotkey**, from inside the game (below);
- the flag on a **tablet or other device** paired with *Show on other devices* ([Tablets, phones and VR](/guide/other-devices#a-tablet-or-another-pc-at-home)). The marks show there too; you make the report on the PC, where the data is.

The top bar then shows **⚑ 1 marked**. A mark keeps the 10 minutes around it for a day, so you can finish your session first and report it later.

![The top bar with a marked moment](/shots/app/topbar-marked.jpg)

### A hotkey for inside the game

**Settings → Agent → Problem reports → Hotkey to mark a moment from inside the game** picks one of a few key combinations (like Ctrl+Alt+M). It works over the game, and a short sound tells you it marked. While it's on, that key does nothing else in any program, so pick one you don't use. If another program already has it, Starglance says so.

## 2. Say what happened

Click **⚑ marked** in the top bar (or **Report a problem** in the tray menu or in **Settings → Agent → Problem reports**):

1. **When**: your mark, *just now*, or something from the activity list of the last 30 minutes.
2. **How much**: how many minutes before and after.
3. **What happened**: what you saw, and what you expected.

![Report a problem: picking the moment](/shots/app/report-pick.jpg)

## 3. Read it, then send it

**Preview the report** builds the file and shows you every part of it before it goes anywhere:

- `report.json`: Starglance's and Windows' versions, the game channel, the window and what you wrote;
- `events.jsonl`: what Starglance made of it (quantum jumps, warnings, seats…);
- `gamelog.txt`: the game's Game.log lines from those minutes;
- `agent.log`: Starglance's own log;
- plus the telemetry itself (aUEC removed) and the game's message definitions, so it can be replayed exactly.

Your handle, other players' names, account and session IDs, IP addresses, email addresses, hub addresses and fleet names are replaced. Your ship, location, server and what happened stay: they're what the report is for. Read it through anyway: a name in a line Starglance doesn't know can slip past.

![The report, ready to send](/shots/app/report-preview.jpg)

Then:

- **Send to your fleet's admins**: through the hub you already use, no account needed. Only that fleet's admins see it, and all of it, including what you don't otherwise share with them. The hub keeps it for 30 days, and you can delete it sooner under **Your account** on the fleet page.
- **Save for a GitHub issue**: saves the file to your Downloads folder, and **Open a GitHub issue** opens the project's bug form, filled in, ready for you to attach it. GitHub issues are public and need a free GitHub account.

## For admins

Reports members send show up under **Admin → Reports** on the hub's page, with a count of new ones. You can read every file in it, download it, mark it, delete it, or **Open a GitHub issue** to pass it on to the project with the form filled in. See [Admin](/hub/admin#problem-reports).

## Switching it off

**Settings → Agent → Problem reports → Keep the last 30 minutes** is on by default. Switching it off stops recording and deletes everything kept so far. Nothing in it ever leaves your PC unless you send a report. See [Privacy](/privacy).
