"""WSJT-X's UDP message protocol: encoding and decoding.

Written to WSJT-X's own description of it, the comment at the top of
``Network/NetworkMessage.hpp``: a big-endian header (magic number, schema
number, message type, the sender's Id), then fields in Qt's QDataStream
format. Schema 3 (QDataStream::Qt_5_4) is what current WSJT-X uses.

Two rules from that file shape the decoder. A message type it does not know
is ignored, not an error; and fields may be added to the end of a message in
later versions, so bytes after the fields it knows are ignored too. A message
that ends *before* a field it needs is malformed, and raises ``ValueError``.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Callable

MAGIC = 0xADBCCBDA
SCHEMA = 3
PULSE_SECONDS = 15
NULL_LENGTH = 0xFFFFFFFF
# Longest Id we accept. WSJT-X's Id is its instance name ("WSJT-X", or the
# --rig-name given), so anything near this is not a real sender.
MAX_ID = 256


class MessageType(IntEnum):
    HEARTBEAT = 0
    STATUS = 1
    DECODE = 2
    CLEAR = 3
    REPLY = 4
    QSO_LOGGED = 5
    CLOSE = 6
    REPLAY = 7
    HALT_TX = 8
    FREE_TEXT = 9
    WSPR_DECODE = 10
    LOCATION = 11
    LOGGED_ADIF = 12
    HIGHLIGHT_CALLSIGN = 13
    SWITCH_CONFIGURATION = 14
    CONFIGURE = 15


# The Decode message's Mode field is the one-character code WSJT-X shows in
# its Band Activity window, not the mode's name: MainWindow::postDecode sends
# the fifth column of the decoded line, which is "~" for FT8.
MODE_CHARACTER = {
    "FT8": "~", "FT4": "+", "JT65": "#", "JT9": "@", "JT4": "$",
    "MSK144": "&", "Q65": ":", "FST4": "`",
}


def mode_character(mode: str) -> str:
    return MODE_CHARACTER.get(mode, mode)


# ---------------------------------------------------------------- encoding


class Writer:
    """Builds one message, field by field, in QDataStream's encoding."""

    def __init__(self) -> None:
        self._parts: list[bytes] = []

    def u8(self, v: int) -> Writer:
        self._parts.append(struct.pack(">B", v))
        return self

    def boolean(self, v: bool) -> Writer:
        return self.u8(1 if v else 0)

    def u32(self, v: int) -> Writer:
        self._parts.append(struct.pack(">I", v))
        return self

    def i32(self, v: int) -> Writer:
        self._parts.append(struct.pack(">i", v))
        return self

    def u64(self, v: int) -> Writer:
        self._parts.append(struct.pack(">Q", v))
        return self

    def f64(self, v: float) -> Writer:
        self._parts.append(struct.pack(">d", v))
        return self

    def utf8(self, v: str | None) -> Writer:
        """A QByteArray: quint32 length, then the bytes. None is the null array."""
        if v is None:
            return self.u32(NULL_LENGTH)
        data = v.encode("utf-8")
        self.u32(len(data))
        self._parts.append(data)
        return self

    def qtime(self, ms_of_day: int) -> Writer:
        """A QTime: milliseconds since midnight."""
        return self.u32(ms_of_day)

    def bytes(self) -> bytes:
        return b"".join(self._parts)


def _header(kind: MessageType, sender: str) -> Writer:
    return Writer().u32(MAGIC).u32(SCHEMA).u32(int(kind)).utf8(sender)


def heartbeat(sender: str, version: str = "qso-graph-sim", revision: str = "") -> bytes:
    return (
        _header(MessageType.HEARTBEAT, sender)
        .u32(SCHEMA).utf8(version).utf8(revision)
        .bytes()
    )


@dataclass
class Status:
    dial_hz: int
    mode: str
    dx_call: str = ""
    report: str = ""
    tx_mode: str = ""
    tx_enabled: bool = False
    transmitting: bool = False
    decoding: bool = False
    rx_df: int = 1500
    tx_df: int = 1500
    de_call: str = ""
    de_grid: str = ""
    dx_grid: str = ""
    tx_watchdog: bool = False
    sub_mode: str = ""
    fast_mode: bool = False
    special_operation: int = 0
    frequency_tolerance: int = NULL_LENGTH  # "not applicable", as WSJT-X sends it
    tr_period: int = 15
    configuration: str = "Default"
    tx_message: str = ""


def status(sender: str, s: Status) -> bytes:
    return (
        _header(MessageType.STATUS, sender)
        .u64(s.dial_hz).utf8(s.mode).utf8(s.dx_call).utf8(s.report).utf8(s.tx_mode or s.mode)
        .boolean(s.tx_enabled).boolean(s.transmitting).boolean(s.decoding)
        .u32(s.rx_df).u32(s.tx_df)
        .utf8(s.de_call).utf8(s.de_grid).utf8(s.dx_grid)
        .boolean(s.tx_watchdog).utf8(s.sub_mode).boolean(s.fast_mode).u8(s.special_operation)
        .u32(s.frequency_tolerance).u32(s.tr_period)
        .utf8(s.configuration).utf8(s.tx_message)
        .bytes()
    )


@dataclass
class Decode:
    is_new: bool
    ms_of_day: int
    snr: int
    dt: float
    df: int
    mode: str  # the one-character code, as sent
    message: str
    low_confidence: bool = False
    off_air: bool = False


def decode(sender: str, d: Decode) -> bytes:
    return (
        _header(MessageType.DECODE, sender)
        .boolean(d.is_new).qtime(d.ms_of_day).i32(d.snr).f64(d.dt).u32(d.df)
        .utf8(d.mode).utf8(d.message).boolean(d.low_confidence).boolean(d.off_air)
        .bytes()
    )


def clear(sender: str) -> bytes:
    return _header(MessageType.CLEAR, sender).bytes()


def close(sender: str) -> bytes:
    return _header(MessageType.CLOSE, sender).bytes()


def replay(target: str) -> bytes:
    """What a receiver sends to ask WSJT-X for the decodes it already has."""
    return _header(MessageType.REPLAY, target).bytes()


# ---------------------------------------------------------------- decoding


class Reader:
    """Reads QDataStream fields; raises ValueError when the message runs out."""

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._at = 0

    def _take(self, n: int) -> bytes:
        if self._at + n > len(self._data):
            raise ValueError(f"message ends at byte {len(self._data)}, a field needs {n} more")
        chunk = self._data[self._at:self._at + n]
        self._at += n
        return chunk

    def u8(self) -> int:
        return int(struct.unpack(">B", self._take(1))[0])

    def boolean(self) -> bool:
        return self.u8() != 0

    def u32(self) -> int:
        return int(struct.unpack(">I", self._take(4))[0])

    def i32(self) -> int:
        return int(struct.unpack(">i", self._take(4))[0])

    def u64(self) -> int:
        return int(struct.unpack(">Q", self._take(8))[0])

    def f64(self) -> float:
        return float(struct.unpack(">d", self._take(8))[0])

    def utf8(self, limit: int = 65_536) -> str | None:
        n = self.u32()
        if n == NULL_LENGTH:
            return None
        if n > limit:
            raise ValueError(f"string of {n} bytes is longer than {limit}")
        return self._take(n).decode("utf-8", errors="replace")

    def qtime(self) -> int:
        return self.u32()

    @property
    def remaining(self) -> int:
        return len(self._data) - self._at


@dataclass
class Message:
    """A decoded message. ``fields`` holds what this type carries, by name."""

    schema: int
    kind: int
    sender: str | None
    fields: dict[str, object] = field(default_factory=dict)

    @property
    def known(self) -> bool:
        return self.kind in MessageType._value2member_map_


def _read_fields(
    r: Reader, into: dict[str, object], spec: list[tuple[str, Callable[[], object]]],
    required: int,
) -> None:
    for i, (name, read) in enumerate(spec):
        if i >= required and not r.remaining:
            return
        into[name] = read()


def parse(data: bytes) -> Message:
    """Decode one datagram. ValueError if it is not a well-formed WSJT-X message."""
    r = Reader(data)
    if r.u32() != MAGIC:
        raise ValueError("not a WSJT-X message (wrong magic number)")
    schema = r.u32()
    kind = r.u32()
    sender = r.utf8(MAX_ID)
    msg = Message(schema=schema, kind=kind, sender=sender)
    f = msg.fields
    if kind == MessageType.HEARTBEAT:
        # "Maximum schema number" arrived with schema 3; older senders stop here.
        if r.remaining:
            f.update(max_schema=r.u32(), version=r.utf8(), revision=r.utf8())
    elif kind == MessageType.STATUS:
        # Status has grown over the years, a field at a time on the end. An older
        # WSJT-X stops sooner, so everything after the first ten is read only if
        # it is there; a message cut off inside the first ten is malformed.
        _read_fields(r, f, [
            ("dial_hz", r.u64), ("mode", r.utf8), ("dx_call", r.utf8), ("report", r.utf8),
            ("tx_mode", r.utf8), ("tx_enabled", r.boolean), ("transmitting", r.boolean),
            ("decoding", r.boolean), ("rx_df", r.u32), ("tx_df", r.u32),
            ("de_call", r.utf8), ("de_grid", r.utf8), ("dx_grid", r.utf8),
            ("tx_watchdog", r.boolean), ("sub_mode", r.utf8), ("fast_mode", r.boolean),
            ("special_operation", r.u8), ("frequency_tolerance", r.u32), ("tr_period", r.u32),
            ("configuration", r.utf8), ("tx_message", r.utf8),
        ], required=10)
    elif kind == MessageType.DECODE:
        f.update(
            is_new=r.boolean(), ms_of_day=r.qtime(), snr=r.i32(), dt=r.f64(), df=r.u32(),
            mode=r.utf8(), message=r.utf8(), low_confidence=r.boolean(), off_air=r.boolean(),
        )
    elif kind == MessageType.WSPR_DECODE:
        f.update(
            is_new=r.boolean(), ms_of_day=r.qtime(), snr=r.i32(), dt=r.f64(),
            frequency_hz=r.u64(), drift_hz=r.i32(), callsign=r.utf8(), grid=r.utf8(),
            power_dbm=r.i32(), off_air=r.boolean(),
        )
    elif kind == MessageType.CLEAR:
        # Window is sent only *to* WSJT-X ("In only"); from WSJT-X it is absent.
        if r.remaining:
            f.update(window=r.u8())
    # Close, Replay and anything this does not know carry nothing more we read.
    return msg
