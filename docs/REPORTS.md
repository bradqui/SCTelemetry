# Problem reports

A player sees something wrong (a quantum jump counted twice, a kill that never showed), clicks **Report a problem**, picks the moment, and gets one file to attach to a GitHub issue. The maintainer replays that file and sees exactly what the agent saw and did.

Decision 24 in SPEC.md. Two ways to send one, both the player's choice: **to their fleet's admins**, through the hub they already use (no new account), or **as a GitHub issue** they attach the file to (a free GitHub account). The agent sends nothing by itself.

## The rolling buffer

While the game sends telemetry, the agent keeps the last **30 minutes** on disk, in `%LOCALAPPDATA%\Starglance\recent\`:

- one gzipped JSON-lines file per minute, in the capture format (`tools/capture.py`, fixtures/README.md), so `run --replay` plays it:
  - `{"t", "frame"}`: each telemetry frame, aUEC removed;
  - `{"t", "log"}`: each Game.log line the agent recognised;
  - `{"t", "event"}`: each event the agent derived;
  - `{"t", "state"}`: connected, streaming, lost, and why;
  - `{"t", "mark"}`: a marked moment.
- compressed as it arrives (about 20 µs a frame, 0.04% of a core) and flushed every few seconds, so a crash loses seconds, not the file;
- about 1–2.5 MB for 30 minutes of play; nothing is written while the game isn't streaming;
- anything older than 30 minutes (clock time, not play time) is deleted, unless a mark keeps it.

Game.log isn't copied: the game keeps it (and older ones in `logbackups`), and a report cuts its window out when it's made.

**Settings → Agent → Problem reports → Keep the last 30 minutes** (on by default). Switching it off deletes the folder.

## Marks

A mark says "this moment": it doesn't have to be made at the time, since the last 30 minutes can be reported anyway, but a marked moment is kept longer.

- **Ways to mark:** the flag button in the page's top bar, the tray menu (**Mark this moment**), or a global hotkey (off by default; Ctrl+Alt+M, Ctrl+Shift+F12 or Ctrl+Alt+F9), which plays a short sound since you're in the game. A paired device (Show on other devices) can mark too, with the flag in its top bar: `POST /api/mark` on lanview, which only adds a mark (decision 25). It sees the marks, but the report is made and sent on the PC, where the data is.
- **The header shows it:** "⚑ 2 marked" next to the flag; clicking it opens the report.
- **Kept:** the 10 minutes around a mark (8 before, 2 after) stay for 24 hours, or until a report is saved from it. At most 20 marks.

## Making a report

**Report a problem** (the header's mark chip, Settings → Agent, or the tray):

1. **When:** a mark, an event from the last 30 minutes ("this one was wrong"), or now.
2. **How much:** 1–8 minutes before and 1–2 after; 3 and 1 by default.
3. **What happened** (required), **what you expected**, and which part (as on the issue form).
4. **Preview:** the report is built and its contents listed; each text file can be read in full, as it will be sent.
5. **Send** it, either way (or both):
   - **Send to my fleet's admins** (when the PC is in a fleet; with several, pick which): the agent uploads the file to that hub with the PC's key. The main button when there's a fleet.
   - **Save for a GitHub issue:** `Starglance-report-<date>-<time>.zip` goes to Downloads and Explorer shows it. **Open a GitHub issue** opens the bug form filled in (what happened, version, game version, part); the player drags the file in. Needs a free GitHub account.

The page says plainly where it goes: GitHub issues are public; a fleet's admins see the whole file, including what the player doesn't share with that fleet (where they were, combat), since that's in Game.log.

## On the hub

- `POST /api/agent/report` (the PC's key): the zip, at most 4 MB. The hub checks it's a report (a zip with `report.json`, only the expected files, not too big unpacked), keeps it in its database with who sent it and from which PC, and reads the summary from `report.json`. At most 10 a day per member.
- **Admin → Reports**: every report, newest first, with the count of new ones on the tab. Each shows who, when, what happened, the agent and game versions; **View** shows the text files; **Download**; **Open a GitHub issue** (the same pre-filled form, saying it came through a fleet hub; the admin drags the file in); a status (*New*, *Forwarded*, *Not a bug*); **Delete**.
- **Your account → Reports you sent**: a member sees and can delete their own.
- Deleted after 30 days (`HUB_REPORT_RETENTION_DAYS`), and with the member's account.
- The hub never contacts GitHub and keeps no GitHub token: GitHub has no way for a program to attach a file to an issue anyway, so the admin's one drag is the same either way.

## The file

| File | What |
|---|---|
| `report.json` | Format version; agent version, Windows build, game channel and version; the window and what it centres on; marks; the player's text; settings that matter (fleets and what they share, by number not address; other devices; updates; hotkey); counts |
| `capture.jsonl.gz` | The buffer's records for the window, cleaned |
| `events.jsonl` | The events the agent derived then, cleaned |
| `gamelog.txt` | Every Game.log line in the window, cleaned |
| `agent.log` | The app's own log for the window, cleaned |
| `telemetry.protoset` | The game's message definitions the agent was using |

## Cleaning

One module (`redact.py`), applied to every text in the report, and the preview shows its result:

- aUEC balances removed (as in captures);
- your handle becomes `<you>`; other players' handles, from the lines the agent recognises (kills, deaths, ships destroyed, ship channels, calibration), become `player-1`, `player-2`… consistently, so events and log lines still match;
- account and session IDs (`playerGEID`, `PlayerId`, `sessionId`, `LoginSessionId`, the login `nickname`) and IP addresses removed;
- hub addresses and fleet names become `<hub-1>`, `<fleet-1>`; any other web address loses its host; your PC's name and Windows user name become `<pc>` and `<user>`; anything shaped like an email address is removed.

Game.log lines the agent doesn't recognise are included, cleaned the same way: they're what a report needs when CIG changes the log. They may hold a name the cleaning can't recognise, which is why the preview shows everything.

## Reading a report

- `starglance run --replay report.zip` plays it in the dashboard, with marks on the timeline.
- Later: `tools/report.py report.zip` (summary, timeline, then-vs-now events from the current code, unrecognised Game.log lines grouped by tag) and `tools/make_fixture.py` from a report, so each fix gets a regression test from the real data.

## Also

The agent runs at below-normal Windows priority, so the game always comes first when the CPU is busy.
