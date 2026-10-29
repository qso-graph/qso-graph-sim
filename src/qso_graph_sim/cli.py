"""The qso-graph-sim command."""

from __future__ import annotations

import argparse
import ipaddress
import re
import signal
import socket
import sys
from collections.abc import Callable, Sequence
from importlib.resources import files
from pathlib import Path

from . import __version__, alltxt
from .player import Player, Station

SAMPLE = "ALL-sample.TXT"
_STAMP = re.compile(r"^\d{6}_\d{6}$")
_CALL = re.compile(r"^[A-Z0-9/]{0,13}$")
_GRID = re.compile(r"^([A-R]{2}\d{2}([A-X]{2})?)?$")


def target(text: str) -> tuple[str, int]:
    """IP:PORT, or [IPv6]:PORT. An address, not a name: nothing is looked up."""
    m = re.match(r"^\[?([^\]]+?)\]?:(\d{1,5})$", text)
    if not m:
        raise argparse.ArgumentTypeError(
            "use IP:PORT, the address QSO Graph Desktop listens on"
        )
    host, port = m.group(1), int(m.group(2))
    try:
        ipaddress.ip_address(host)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{host} is not an IP address") from None
    if not 0 < port < 65536:
        raise argparse.ArgumentTypeError(f"{port} is not a port")
    return host, port


def _matching(
    pattern: re.Pattern[str], what: str, upper: bool = False
) -> Callable[[str], str]:
    def check(text: str) -> str:
        if text == "":
            return text  # the default: not given
        value = text.upper() if upper else text
        if not pattern.match(value):
            raise argparse.ArgumentTypeError(f"{text!r} is not {what}")
        return value
    return check


def _speed(text: str) -> float:
    try:
        v = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r} is not a number") from None
    if not 0 < v <= 1000:
        raise argparse.ArgumentTypeError("speed is more than 0 and at most 1000")
    return v


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="qso-graph-sim",
        description=(
            "Replays what a ham radio program sends on the network, from its own log, "
            "so a receiver can be tested without a radio."
        ),
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    app = p.add_mutually_exclusive_group(required=True)
    app.add_argument("--wsjtx", action="store_true",
                     help="WSJT-X: play an ALL.TXT as its UDP messages")
    p.add_argument("--to", type=target, required=True, metavar="IP:PORT",
                   help="where to send: the receiver's address and port (WSJT-X uses 2237)")
    p.add_argument("--file", type=Path, metavar="PATH",
                   help="the log to play (default: a sample of 20 m FT8, 120 decodes)")
    p.add_argument("--from", dest="start", type=_matching(_STAMP, "YYMMDD_HHMMSS"),
                   default="", metavar="YYMMDD_HHMMSS", help="start at this time in the log")
    p.add_argument("--id", default="WSJT-X", metavar="NAME",
                   type=_matching(re.compile(r"^.{1,64}$"), "an Id"),
                   help="the instance name to send as (WSJT-X's default is WSJT-X)")
    p.add_argument("--call", default="", type=_matching(_CALL, "a callsign", upper=True),
                   help="your callsign, sent in Status")
    p.add_argument("--grid", default="", type=_matching(_GRID, "a 4- or 6-character grid"),
                   help="your grid, sent in Status")
    p.add_argument("--speed", type=_speed, default=1.0, metavar="N",
                   help="play faster than real time, for testing (default 1)")
    p.add_argument("--loop", action="store_true", help="start again at the end")
    return p


def _read(path: Path | None) -> tuple[str, str]:
    if path is None:
        sample = files("qso_graph_sim").joinpath("samples", SAMPLE)
        return sample.read_text("utf-8"), "the sample"
    return path.read_text("utf-8", errors="replace"), str(path)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        text, name = _read(args.file)
    except OSError as e:
        print(f"qso-graph-sim: cannot read {args.file}: {e.strerror}", file=sys.stderr)
        return 1
    log = alltxt.read(text, args.start)
    if not log.cycles:
        print(f"qso-graph-sim: no received decodes in {name}"
              + (f" from {args.start}" if args.start else ""), file=sys.stderr)
        return 1
    print(f"{len(log.cycles)} cycles, {log.decodes} decodes from {name}"
          + (f" ({log.skipped} lines skipped: Tx or not a decode)" if log.skipped else ""))
    host, port = args.to
    family = socket.AF_INET6 if ipaddress.ip_address(host).version == 6 else socket.AF_INET
    with socket.socket(family, socket.SOCK_DGRAM) as sock:
        print(f"sending to {host}:{port} as {args.id}; Ctrl+C to stop")
        player = Player(
            sock=sock, target=(host, port), log=log,
            station=Station(sender=args.id, call=args.call, grid=args.grid),
            speed=args.speed, loop=args.loop,
        )
        signal.signal(signal.SIGTERM, lambda *_: player.stop())
        try:
            player.run()
        except KeyboardInterrupt:
            player.stop()
        except OSError as e:
            print(f"qso-graph-sim: cannot send to {host}:{port}: {e.strerror}",
                  file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
