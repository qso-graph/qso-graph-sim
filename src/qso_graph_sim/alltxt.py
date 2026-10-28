"""Reading WSJT-X's ALL.TXT, the log of every decode it has made.

One line per decode, in the format WSJT-X has written since 2.x::

    260407_233915    14.074 Rx FT8    -12  0.2 1234 CQ K7ABC DN13

date_time (UTC), dial frequency in MHz, Rx or Tx, mode, SNR in dB, DT in
seconds, audio offset in Hz, then the message.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

_LINE = re.compile(
    r"^(\d{6}_\d{6})\s+(\d+(?:\.\d+)?)\s+(Rx|Tx)\s+(\S+)\s+(-?\d+)\s+(-?\d+(?:\.\d+)?)"
    r"\s+(\d+)\s+(.+?)\s*$"
)
# WSJT-X marks a decode it has low confidence in with a trailing "?"; it is
# not part of the message that was sent.
_LOW_CONFIDENCE = re.compile(r"\s\?$")


@dataclass(frozen=True)
class Line:
    stamp: str          # as written: YYMMDD_HHMMSS
    utc: datetime
    dial_hz: int
    direction: str      # "Rx" or "Tx"
    mode: str           # the mode's name, e.g. "FT8"
    snr: int
    dt: float
    df: int
    message: str
    low_confidence: bool


def parse_line(text: str) -> Line | None:
    """One ALL.TXT line, or None if it is not one."""
    m = _LINE.match(text)
    if not m:
        return None
    stamp, mhz, direction, mode, snr, dt, df, message = m.groups()
    try:
        utc = datetime.strptime(stamp, "%y%m%d_%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    low = bool(_LOW_CONFIDENCE.search(message))
    return Line(
        stamp=stamp,
        utc=utc,
        dial_hz=round(float(mhz) * 1_000_000),
        direction=direction,
        mode=mode,
        snr=int(snr),
        dt=float(dt),
        df=int(df),
        message=_LOW_CONFIDENCE.sub("", message) if low else message,
        low_confidence=low,
    )


@dataclass
class Cycle:
    """The decodes of one T/R period on one dial frequency."""

    stamp: str
    dial_hz: int
    mode: str
    decodes: list[Line] = field(default_factory=list)


@dataclass
class Log:
    cycles: list[Cycle]
    skipped: int  # Tx lines and lines that are not decodes

    @property
    def decodes(self) -> int:
        return sum(len(c.decodes) for c in self.cycles)


def read(text: str, start: str = "") -> Log:
    """Group received decodes into cycles, in file order, from ``start`` on."""
    cycles: list[Cycle] = []
    skipped = 0
    for raw in text.splitlines():
        if not raw.strip():
            continue
        line = parse_line(raw)
        if line is None or line.direction != "Rx":
            skipped += 1
            continue
        if start and line.stamp < start:
            continue
        last = cycles[-1] if cycles else None
        if last and last.stamp == line.stamp and last.dial_hz == line.dial_hz:
            last.decodes.append(line)
        else:
            cycles.append(Cycle(line.stamp, line.dial_hz, line.mode, [line]))
    return Log(cycles, skipped)
