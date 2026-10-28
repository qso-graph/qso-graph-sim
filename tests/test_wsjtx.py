"""The protocol, checked against WSJT-X's own description of it."""

from __future__ import annotations

import struct

import pytest

from qso_graph_sim import wsjtx


def test_heartbeat_bytes_are_exactly_as_the_header_describes() -> None:
    got = wsjtx.heartbeat("WSJT-X", version="3.3.0", revision="abc")
    want = (
        struct.pack(">III", 0xADBCCBDA, 3, 0)     # magic, schema 3, Heartbeat
        + struct.pack(">I", 6) + b"WSJT-X"        # Id as a QByteArray
        + struct.pack(">I", 3)                    # maximum schema number
        + struct.pack(">I", 5) + b"3.3.0"
        + struct.pack(">I", 3) + b"abc"
    )
    assert got == want


def test_decode_round_trip() -> None:
    d = wsjtx.Decode(
        is_new=True, ms_of_day=(23 * 3600 + 39 * 60 + 15) * 1000, snr=-12, dt=0.2,
        df=1234, mode="~", message="CQ K7ABC DN13", low_confidence=False, off_air=False,
    )
    msg = wsjtx.parse(wsjtx.decode("WSJT-X", d))
    assert (msg.schema, msg.kind, msg.sender) == (3, wsjtx.MessageType.DECODE, "WSJT-X")
    assert msg.fields == {
        "is_new": True, "ms_of_day": d.ms_of_day, "snr": -12, "dt": 0.2, "df": 1234,
        "mode": "~", "message": "CQ K7ABC DN13", "low_confidence": False, "off_air": False,
    }


def test_status_round_trip() -> None:
    s = wsjtx.Status(dial_hz=14_074_000, mode="FT8", de_call="KI7MT", de_grid="DN13",
                     decoding=True)
    f = wsjtx.parse(wsjtx.status("WSJT-X", s)).fields
    assert f["dial_hz"] == 14_074_000
    assert f["mode"] == "FT8" and f["tx_mode"] == "FT8"
    assert f["de_call"] == "KI7MT" and f["de_grid"] == "DN13"
    assert f["decoding"] is True and f["tr_period"] == 15
    assert f["frequency_tolerance"] == 0xFFFFFFFF
    assert f["configuration"] == "Default"


def test_an_older_shorter_status_is_still_read() -> None:
    full = wsjtx.status("WSJT-X", wsjtx.Status(dial_hz=7_074_000, mode="FT8"))
    # Cut it after Tx DF: the ten fields every version has sent.
    header = 4 + 4 + 4 + 4 + 6
    first_ten = header + 8 + (4 + 3) + 4 + 4 + (4 + 3) + 1 + 1 + 1 + 4 + 4
    f = wsjtx.parse(full[:first_ten]).fields
    assert f["dial_hz"] == 7_074_000 and f["tx_df"] == 1500
    assert "de_call" not in f


def test_a_message_cut_inside_a_required_field_is_refused() -> None:
    data = wsjtx.decode("WSJT-X", wsjtx.Decode(True, 0, -1, 0.0, 100, "~", "CQ TEST"))
    with pytest.raises(ValueError):
        wsjtx.parse(data[:-5])


def test_bytes_after_the_known_fields_are_ignored() -> None:
    data = wsjtx.decode("WSJT-X", wsjtx.Decode(True, 0, -1, 0.0, 100, "~", "CQ TEST"))
    assert wsjtx.parse(data + b"\x00\x01\x02").fields["message"] == "CQ TEST"


def test_an_unknown_type_is_not_an_error() -> None:
    data = struct.pack(">III", 0xADBCCBDA, 3, 99) + struct.pack(">I", 6) + b"WSJT-X" + b"xx"
    msg = wsjtx.parse(data)
    assert msg.kind == 99 and not msg.known and msg.fields == {}


@pytest.mark.parametrize("data", [
    b"",
    b"\x00" * 20,
    struct.pack(">III", 0xADBCCBDA, 3, 2) + struct.pack(">I", 10_000) + b"x",
])
def test_garbage_is_refused(data: bytes) -> None:
    with pytest.raises(ValueError):
        wsjtx.parse(data)


def test_null_and_empty_strings_differ() -> None:
    r = wsjtx.Reader(wsjtx.Writer().utf8(None).utf8("").bytes())
    assert r.utf8() is None
    assert r.utf8() == ""


def test_replay_clear_close_carry_only_the_header() -> None:
    for build, kind in [(wsjtx.replay, 7), (wsjtx.clear, 3), (wsjtx.close, 6)]:
        msg = wsjtx.parse(build("WSJT-X"))
        assert (msg.kind, msg.sender, msg.fields) == (kind, "WSJT-X", {})


def test_mode_characters() -> None:
    assert wsjtx.mode_character("FT8") == "~"
    assert wsjtx.mode_character("FT4") == "+"
    assert wsjtx.mode_character("SOMETHING") == "SOMETHING"
