"""Reading ALL.TXT."""

from __future__ import annotations

from importlib.resources import files

from qso_graph_sim import alltxt

SAMPLE = files("qso_graph_sim").joinpath("samples", "ALL-sample.TXT").read_text("utf-8")


def test_a_line() -> None:
    line = alltxt.parse_line("260407_233915    14.074 Rx FT8    -12  0.2 1234 CQ K7ABC DN13")
    assert line is not None
    assert line.stamp == "260407_233915"
    assert line.utc.isoformat() == "2026-04-07T23:39:15+00:00"
    assert (line.dial_hz, line.direction, line.mode) == (14_074_000, "Rx", "FT8")
    assert (line.snr, line.dt, line.df) == (-12, 0.2, 1234)
    assert line.message == "CQ K7ABC DN13" and not line.low_confidence


def test_a_hashed_callsign_stays_as_written() -> None:
    line = alltxt.parse_line(
        "260407_235830    14.074 Rx FT8     -9  1.2  783 <W1AW/5> W5DV +10"
    )
    assert line is not None and line.message == "<W1AW/5> W5DV +10"


def test_low_confidence_mark_is_a_flag_not_message_text() -> None:
    line = alltxt.parse_line(
        "260407_233915    14.074 Rx FT8    -24  0.1  500 K1ABC W9XYZ R-10 ?"
    )
    assert line is not None
    assert line.low_confidence and line.message == "K1ABC W9XYZ R-10"


def test_not_a_decode() -> None:
    for text in ["", "garbage", "261399_999999    14.074 Rx FT8  -1 0.1 100 CQ X"]:
        assert alltxt.parse_line(text) is None


def test_the_sample_groups_into_its_cycles() -> None:
    log = alltxt.read(SAMPLE)
    assert log.decodes == 120 and log.skipped == 0
    assert [len(c.decodes) for c in log.cycles] == [15, 20, 14, 26, 19, 9, 17]
    assert {c.dial_hz for c in log.cycles} == {14_074_000}


def test_tx_lines_are_skipped_and_counted() -> None:
    text = (
        "260407_233915    14.074 Tx FT8      0  0.0 1500 CQ KI7MT DN13\n"
        "260407_233915    14.074 Rx FT8    -12  0.2 1234 CQ K7ABC DN13\n"
    )
    log = alltxt.read(text)
    assert log.decodes == 1 and log.skipped == 1


def test_start_from_a_time() -> None:
    log = alltxt.read(SAMPLE, start="260407_233915")
    assert log.cycles[0].stamp == "260407_233915" and log.decodes == 26 + 19 + 9 + 17


def test_a_band_change_starts_a_new_cycle() -> None:
    text = (
        "260407_233915    14.074 Rx FT8    -12  0.2 1234 CQ K7ABC DN13\n"
        "260407_233915    24.915 Rx FT8    -12  0.2 1234 CQ W1AW FN31\n"
    )
    assert [c.dial_hz for c in alltxt.read(text).cycles] == [14_074_000, 24_915_000]
