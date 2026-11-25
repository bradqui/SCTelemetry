# Command line

Everything in Settings can also be done from a terminal. In the folder with `starglance.exe`:

```
starglance on                 # switch the game's telemetry on (backs up user.cfg)
starglance link <invite>      # join a fleet with the invite link from your org's admin
starglance run --open         # the cockpit view in your browser, and send to the fleet
```

`starglance.exe` is a windowed app, so in PowerShell or cmd the prompt can come back before its output. `start /wait starglance.exe installs` waits for it.

| Command | Does |
|---|---|
| `app` | The Windows app, with its tray icon and window (what double-clicking does) |
| `run` | The agent without a window: reads the game, serves the cockpit view, sends to your fleets. `--open` opens the view in your browser |
| `link <invite>` | Join a fleet with an invite link (`--name` picks your display name), or link another PC with the hub's address |
| `open` | Open your fleet's page in your browser, signed in |
| `unlink` | Stop sending to a fleet and forget its key |
| `share` | Show or change what you share: `share --off vitals uec`, `share --on vitals` |
| `installs` | List your Star Citizen installs and whether telemetry is on |
| `status` | Telemetry settings for one channel |
| `on` / `off` | Switch the game's telemetry on or off. `off` puts `user.cfg` back exactly |
| `probe` | Check that the running game's telemetry server answers |
| `protoset` | Extract the telemetry message definitions from `StarCitizen.exe` |

In several fleets, `--hub <address>` picks which one `open`, `unlink` and `share` mean. `--channel PTU` (or EPTU, TECH-PREVIEW, HOTFIX) picks a game channel, and `--path` your StarCitizen folder if it isn't found by itself.

`starglance <command> --help` lists every option.
