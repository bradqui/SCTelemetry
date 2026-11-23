"""Command line for the agent's setup pieces (the tray app comes later).

python -m fleet_agent installs
python -m fleet_agent status  [--channel LIVE]
python -m fleet_agent on      [--channel LIVE]
python -m fleet_agent off     [--channel LIVE]
python -m fleet_agent protoset [--channel LIVE] [--out telemetry.protoset] [--force]
python -m fleet_agent probe   [--channel LIVE]
"""

from __future__ import annotations

import argparse
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
    env = winenv.get_user_env()
    print(f"  {winenv.ENV_NAME} = {env if env is not None else '(not set)'}")
    backups = gamecfg.existing_backups(inst.user_cfg)
    if backups:
        print(f"  backup: {backups[0]}")


def cmd_on(args) -> None:
    inst = _pick(args)
    result = switch.switch_on(inst, actions=args.actions)
    if result.cfg.changed:
        print(f"Updated {inst.user_cfg}")
        if result.cfg.backup:
            print(f"  backup saved as {result.cfg.backup.name}")
    else:
        print(f"{inst.user_cfg} already has telemetry on.")
    if result.env_changed:
        print(f"Set the Windows user variable {winenv.ENV_NAME}={winenv.ENV_VALUE}.")
    if result.cfg.changed or result.env_changed:
        print(switch.RESTART_NOTE)


def cmd_off(args) -> None:
    inst = _pick(args)
    result = switch.switch_off(inst)
    print(
        f"Reverted our settings in {inst.user_cfg}."
        if result.cfg.changed
        else f"{inst.user_cfg} had nothing of ours to revert."
    )
    if result.env_changed:
        print(f"Reverted the Windows user variable {winenv.ENV_NAME}.")


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

    channel = client.open_channel(port=args.port)
    print(f"Connecting to 127.0.0.1:{args.port} ...")
    if not client.wait_ready(channel, timeout=args.timeout):
        sys.exit("Nothing is listening. Is the game running with telemetry switched on?")
    try:
        from .schema import TelemetrySchema

        schema = TelemetrySchema.from_reflection(channel)
        print("Server reflection: AVAILABLE")
    except Exception as exc:  # noqa: BLE001 - report any failure mode
        print(f"Server reflection: not available ({type(exc).__name__}: {exc})")
        inst = _pick(args)
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

    add("installs", cmd_installs, "List Star Citizen installs and whether telemetry is on")
    add("status", cmd_status, "Show telemetry settings for a channel")
    add("on", cmd_on, "Switch telemetry on (edits user.cfg, sets the env var)").add_argument(
        "--actions", action="store_true", help="Also allow game actions (later phase)"
    )
    add("off", cmd_off, "Switch telemetry off (reverts our settings)")
    p = add("protoset", cmd_protoset, "Extract the telemetry definitions from StarCitizen.exe")
    p.add_argument("--out", help="Also write a .protoset file here")
    p.add_argument("--force", action="store_true", help="Ignore the cache")
    p = add("probe", cmd_probe, "Check the running game's telemetry server")
    p.add_argument("--port", type=int, default=50051)
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
