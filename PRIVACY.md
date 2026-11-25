# Privacy

Starglance has two parts: the **agent**, which runs on your gaming PC, and the **hub**, which your org runs on its own server. Nobody else is involved. There is no central service, no analytics, no ads and no tracking. The project's authors don't receive anything from your agent or your org's hub.

## The agent (starglance.exe)

**What it reads, on your PC only**

- The game's **telemetry stream**, which the game offers on your own PC (`127.0.0.1`) once telemetry is switched on: ship, flight, warning lights, fuel, power, weapons, your vitals, seat and role. If the game's server doesn't describe its messages, the agent reads them from `StarCitizen.exe` (read-only).
- The game's **Game.log** (read-only), for what the stream lacks: your location in game terms (armistice zone, jurisdiction, server, star system), quantum routes, contracts, kills and losses, injuries, the ship you're aboard, and your in-game handle.
- The game's **user.cfg**, only when you switch telemetry on or off (Agent settings, or `starglance on` / `off`). It keeps a backup and restores the file exactly when you switch it off.

It never reads game memory, never touches Easy Anti-Cheat and never sends anything to the game.

**What it sends, and where**

- **Your cockpit view** is served on `127.0.0.1` and accepts connections from this PC only.
- **Other devices**, only if you switch on *Show on other devices* (Settings → Agent): the same view, view only, on your home network (port 8741), to devices you've paired with a code shown on this PC. A paired device can also mark a moment for a problem report, which only tells this PC to keep those minutes; reports are made and sent on this PC. The connection is plain HTTP, so someone who can watch your network's traffic could see it too. Switching it off closes the port.
- **To the hubs of the fleets you join, and nowhere else.** A hub's address is in the invite link from that org's admin. You can be in several fleets (one per org); each hub gets only what you share with that fleet, and nothing while you've switched that fleet off. To each, it sends:
  - when you join: your display name and your PC's name, so you can tell your PCs apart;
  - while it runs: what you choose to share with that fleet (Agent settings, or `starglance share --hub <fleet>`). The categories are status (in game, on foot or seated, your seat, your in-game handle), ship, weapons, vitals, uec, location, mission and combat. Everything is on by default. Anything you switch off never leaves your PC.
- **Update notices**: when it starts and every few hours, and when you click **Check now** (Settings → Agent → Updates), the agent asks this project's GitHub page which release is the latest (one request to `github.com/bradqui/starglance/releases/latest`; the answer is a redirect naming the version). GitHub sees your IP address and that it's Starglance, as for any web request; nothing about you or your game is sent. Switch it off under **Settings → Agent → Updates → Check for new versions**. Your org's hub also says which agent version is current.
- **Updates**, only when you click **Update** or switch on *Update automatically* (Settings → Agent; off by default): the app downloads that version's `starglance.exe` and its checksum file from this project's GitHub releases, and nothing else. GitHub sees the download, as for any download from a browser; nothing about you or your game is sent. The address is fixed in the app; a hub can only say which version is current, not where to download it.

- **A problem report, only when you click Send** (Report a problem → *Send to my fleet's admins*): the report file goes to the hub of the fleet you pick, with this PC's key. Its admins see the whole file: a few minutes of your telemetry, Game.log and Starglance's log, with names, IDs and addresses taken out, including what you don't otherwise share with that fleet (where you were, combat). You see all of it before sending.

If you never join a fleet, the agent sends nothing anywhere.

**What it stores on your PC**

- The key that links this PC to your org's hub, in Windows Credential Manager.
- Its settings (hub address, what you share, your display name), its window's size and position, the page's own storage (your dashboard layouts and theme), caches and a log file, all in `%LOCALAPPDATA%\Starglance`.
- **Paired devices**, if you use *Show on other devices*: for each, a rough name ("Safari on iPad"), when it was paired and last seen, and a hash of its key, in `other-devices.json` in the same folder. The device keeps the key in a cookie.
- **Updates**: whether automatic updates are on, and the last version installed that way, in `updates.json`. While updating, the previous exe sits next to the new one as `starglance.old.exe` for a few seconds.
- **Start with Windows**, only if you switch it on (Settings → Agent, or the tray menu): one value named `Starglance` under `HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run`, which starts it in the tray when you sign in. Switching it off removes the value.
- **The last 30 minutes, for problem reports** (Settings → Agent → Problem reports; on by default): what the game sent and what Starglance made of it, in `recent\`, with aUEC amounts removed. Anything older is deleted, except the 10 minutes around a moment you mark, which stay for a day. Switching it off deletes it all. It never leaves your PC by itself.
- **Problem reports**, only when you make one: a file in your Downloads folder with the minutes you picked, the game's Game.log lines for them and Starglance's own log. Your handle, other players' names, account and session IDs, IP addresses, hub addresses and fleet names are replaced; you see all of it before it's saved. You choose whether to send it to your fleet's admins (above) or attach it to a GitHub issue, which is public. A hotkey to mark a moment, if you pick one, is registered with Windows only while Starglance runs.
- Recordings, only if you run the capture tool yourself (`tools/capture.py`, from the source code). They stay in a local folder, with aUEC amounts removed.

**Stopping**

- To stop sharing something, switch it off in Agent settings.
- To stop sending to a fleet for a while, switch it off in Agent settings. To leave it, use **Leave** (or `starglance unlink --hub <fleet>`): its hub forgets this PC and the key is deleted from Credential Manager.
- To switch the game's telemetry off, use Agent settings or `starglance off`.
- To remove the agent, switch off *Start with Windows* if you switched it on, then delete `starglance.exe` and the folder `%LOCALAPPDATA%\Starglance`. It doesn't install anything else.

## The hub (your org's server)

**Whoever runs your org's hub can see everything you share.** The hub keeps:

- your account: display name; your Discord ID and avatar if you connect Discord;
- your linked PCs: name, when last seen, and a hash of each PC's key;
- the browsers signed in as you: a rough device name ("Safari on iPhone"), how and when they signed in, and when they were last active;
- fleet events (seat changes, quantum jumps, contracts, kills…) for 30 days, by default;
- problem reports you chose to send to the admins, for 30 days by default; you can delete yours under **Your account**;
- live state (what you share right now) in memory only, while you're online.

Org members see the fleet page. The org's admins can also manage members and invites, and can create API keys for bots, which can read the same fleet information.

On the hub's fleet page, **Your account** lets you unlink PCs, sign out devices and delete your account. Deleting your account removes your history from the hub.

## Questions

Open an issue at https://github.com/bradqui/starglance/issues. For your org's data, ask whoever runs your hub.
