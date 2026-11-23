"""Command line for the agent (the tray app comes later).

python -m fleet_agent run     [--open] [--game-port 2943] [--ui-port 8740]
python -m fleet_agent run     --replay [FILES...] [--speed 1] [--open]
python -m fleet_agent installs
python -m fleet_agent status  [--channel LIVE]
python -m fleet_agent on      [--channel LIVE]
python -m fleet_agent off     [--channel LIVE]
python -m fleet_agent protoset [--channel LIVE] [--out telemetry.protoset] [--force]
python -m fleet_agent probe   [--channel LIVE]
"""

from __future__ import annotations

import argparse
import contextlib
import logging
import sys
from pathlib import Path

from . import gamecfg, installs, paths, protoset, switch, winenv
from .installs import Install


def _pick(args) -> Install:
    extra = [Path(args.path)] if args.path else []
    found = installs.find_installs(extra)
    if args.path and found:
        installs.remember_root(Path(args.path))
    if args.channel:
        match = [i for i in found if i.channel == args.channel.upper()]
        if not match:
            sys.exit(
                f"No {args.channel.upper()} install found. Found: {_names(found) or 'none'}. "
                "Use --path to point at your StarCitizen folder."
            )
        return match[0]
    if len(found) == 1:
        return found[0]
    live = [i for i in found if i.channel == "LIVE"]
    if live:
        return live[0]
    sys.exit(f"Pick a channel with --channel. Found: {_names(found) or 'none'}.")


def _names(found: list[Install]) -> str:
    return ", ".join(f"{i.channel}" for i in found)


def _find(args) -> Install | None:
    """Like _pick, but None instead of exiting (e.g. replaying on a PC without the game)."""
    try:
        return _pick(args)
    except SystemExit:
        return None


def cmd_run(args) -> None:
    import asyncio
    import webbrowser

    from .gamelog import GameLogTail
    from .localserver import LocalServer
    from .runtime import GameReader, Pipeline, ReplaySource

    playhead = None
    if args.replay is not None:
        from .replay import FIXTURES_DIR, Playhead, Recording, default_fixtures

        files = [Path(f) for f in args.replay] or default_fixtures(FIXTURES_DIR)
        if not files:
            sys.exit("No recordings to replay.")
        print(f"Indexing {len(files)} recording(s)...")
        playhead = Playhead(Recording.load(files), speed=args.speed)

    async def run() -> None:
        tail = None
        pipeline = Pipeline()
        server = LocalServer(pipeline, port=args.ui_port, playhead=playhead)
        await server.start()
        loop = asyncio.get_running_loop()
        if playhead is not None:
            reader = ReplaySource(pipeline, loop, playhead)
            rec = playhead.rec
            source = (
                f"Replaying {len(rec.chapters)} recording(s), {rec.duration / 60:.1f} min, "
                f"{len(rec.markers)} events. Use the timeline at the bottom of the page."
            )
        else:
            install = _find(args)
            reader = GameReader(pipeline, loop, install=install, port=args.game_port)
            if install is not None:
                tail = GameLogTail(
                    install.game_log,
                    lambda line, quiet: loop.call_soon_threadsafe(
                        lambda: pipeline.on_log(line, None, quiet)
                    ),
                )
            game = f"port {args.game_port}" if args.game_port else "port from Game.log"
            source = f"Game: {install.channel if install else 'no install found'}, {game}."
        reader.start()
        if tail is not None:
            tail.start()
        url = f"http://127.0.0.1:{server.port}/"
        print(f"Fleet Telemetry agent: local view at {url}")
        print(f"{source} Ctrl+C stops.")
        if args.open:
            webbrowser.open(url)
        try:
            await asyncio.Event().wait()
        finally:
            reader.stop()
            if tail is not None:
                tail.stop()
            await server.stop()

    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(run())


def cmd_installs(args) -> None:
    found = installs.find_installs([Path(args.path)] if args.path else [])
    if not found:
        print("No Star Citizen installs found. Use --path to point at your StarCitizen folder.")
        return
    for inst in found:
        st = gamecfg.status(inst.user_cfg)
        flag = "ON " if st.telemetry_enabled else "off"
        print(f"[{flag}] {inst.channel:<13} {inst.path}")


def cmd_status(args) -> None:
    inst = _pick(args)
    st = gamecfg.status(inst.user_cfg)
    print(f"{inst.channel}: {inst.user_cfg}{'' if st.exists else '  (missing)'}")
    print(f"  telemetry: {'ON' if st.telemetry_enabled else 'off'}")
    print(f"  game actions: {'ON' if st.actions_enabled else 'off'}")
    for key, value in st.values.items():
        print(f"    {key} = {value if value is not None else '(not set)'}")
    from . import client

    port = client.port_from_log(inst.game_log)
    print(f"  port in last Game.log: {port or '(none: telemetry was off, or no game run yet)'}")
    backups = gamecfg.existing_backups(inst.user_cfg)
    if backups:
        print(f"  backup: {backups[0]}")


def cmd_on(args) -> None:
    inst = _pick(args)
    result = switch.switch_on(inst, actions=args.actions)
    if result.cfg.changed:
        print(f"Done: switched telemetry on in {inst.user_cfg}")
        if result.cfg.backup:
            print(f"      (your original was saved as {result.cfg.backup.name})")
    else:
        print(f"Already done: {inst.user_cfg} has telemetry on.")
    if result.env_changed:
        print(f"Done: removed the Windows variable {winenv.ENV_NAME} (the game doesn't need it).")
    if result.cfg.changed:
        print(f"\nOne thing left for you: {switch.RESTART_NOTE}")


def cmd_off(args) -> None:
    inst = _pick(args)
    result = switch.switch_off(inst)
    print(
        f"Done: switched telemetry off in {inst.user_cfg}."
        if result.cfg.changed
        else f"Nothing to do: {inst.user_cfg} had none of our settings."
    )
    if result.env_changed:
        print(f"Done: removed the Windows variable {winenv.ENV_NAME}.")


def cmd_protoset(args) -> None:
    inst = _pick(args)
    print(f"Reading {inst.exe} ...")
    file_set, cached = protoset.load_or_extract(
        inst.exe, paths.protoset_cache_dir(), force=args.force
    )
    print(f"Cached at {cached}")
    if args.out:
        protoset.write_protoset(file_set, Path(args.out))
        print(f"Wrote {args.out}")
        print(f"  grpcurl -plaintext -protoset {args.out} 127.0.0.1:50051 list")
    from .schema import TelemetrySchema

    schema = TelemetrySchema.from_file_set(file_set, "exe")
    print(f"{len(file_set.file)} file(s): " + ", ".join(f.name for f in file_set.file))
    print(schema.describe())


def cmd_probe(args) -> None:
    from . import client

    inst = _pick(args)
    port = args.port or client.discover_port(inst.game_log)
    channel = client.open_channel(port=port)
    print(f"Connecting to 127.0.0.1:{port} ...")
    if not client.wait_ready(channel, timeout=args.timeout):
        sys.exit(
            "Nothing is listening. Is the game running and loaded in, with telemetry "
            "switched on (python -m fleet_agent status)?"
        )
    try:
        from .schema import TelemetrySchema

        schema = TelemetrySchema.from_reflection(channel)
        print("Server reflection: AVAILABLE")
    except Exception:  # noqa: BLE001 - any failure means "use the exe"
        print("Server reflection: not offered (using definitions from StarCitizen.exe)")
        schema = client.load_schema(channel, inst.exe, prefer_reflection=False)
    print(schema.describe())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fleet_agent", description="Fleet Telemetry agent tools")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name, func, help_text):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--channel", help="LIVE, PTU, EPTU, TECH-PREVIEW or HOTFIX")
        p.add_argument("--path", help="Your StarCitizen folder, if it isn't found automatically")
        p.set_defaults(func=func)
        return p

    p = add("run", cmd_run, "Run the agent: read the game, serve the local view")
    p.add_argument("--open", action="store_true", help="Open the local view in your browser")
    p.add_argument("--game-port", type=int, help="Default: from Game.log (replay: 2943)")
    p.add_argument("--ui-port", type=int, default=8740, help="Local view port (default 8740)")
    p.add_argument(
        "--replay",
        nargs="*",
        metavar="FILE",
        help="No game: replay recordings with a timeline in the page (default: all fixtures)",
    )
    p.add_argument("--speed", type=float, default=1.0, help="Replay speed (default 1)")
    add("installs", cmd_installs, "List Star Citizen installs and whether telemetry is on")
    add("status", cmd_status, "Show telemetry settings for a channel")
    add("on", cmd_on, "Switch telemetry on (edits user.cfg)").add_argument(
        "--actions", action="store_true", help="Also allow game actions (later phase)"
    )
    add("off", cmd_off, "Switch telemetry off (reverts our settings)")
    p = add("protoset", cmd_protoset, "Extract the telemetry definitions from StarCitizen.exe")
    p.add_argument("--out", help="Also write a .protoset file here")
    p.add_argument("--force", action="store_true", help="Ignore the cache")
    p = add("probe", cmd_probe, "Check the running game's telemetry server")
    p.add_argument("--port", type=int, help="Default: read from Game.log, else 2942")
    p.add_argument("--timeout", type=float, default=3.0)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING)
    try:
        args.func(args)
    except (gamecfg.CfgWriteError, protoset.ExtractionError) as exc:
        sys.exit(str(exc))


if __name__ == "__main__":
    main()
