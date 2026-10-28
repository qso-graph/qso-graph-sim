"""The command line refuses what it cannot use, and says why."""

from __future__ import annotations

import argparse

import pytest

from qso_graph_sim import cli


@pytest.mark.parametrize("text, want", [
    ("192.168.1.50:2237", ("192.168.1.50", 2237)),
    ("[::1]:2237", ("::1", 2237)),
])
def test_target(text: str, want: tuple[str, int]) -> None:
    assert cli.target(text) == want


@pytest.mark.parametrize("text", [
    "192.168.1.50", "localhost:2237", "example.com:2237", "192.168.1.50:0",
    "192.168.1.50:70000", "300.1.1.1:2237",
])
def test_target_refused(text: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        cli.target(text)


def test_an_app_is_required(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["--to", "127.0.0.1:2237"])
    assert "--wsjtx" in capsys.readouterr().err


@pytest.mark.parametrize("args", [
    ["--from", "2026-04-07"], ["--grid", "ZZ99"], ["--call", "K1 ABC"],
    ["--speed", "0"], ["--speed", "fast"],
])
def test_bad_options(args: list[str]) -> None:
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["--wsjtx", "--to", "127.0.0.1:2237", *args])


def test_callsign_is_upper_cased() -> None:
    a = cli.build_parser().parse_args(["--wsjtx", "--to", "127.0.0.1:2237", "--call", "ki7mt"])
    assert a.call == "KI7MT"


def test_a_missing_file_is_an_error_not_a_traceback(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = cli.main(["--wsjtx", "--to", "127.0.0.1:2237", "--file", "/nonexistent/ALL.TXT"])
    assert rc == 1 and "cannot read" in capsys.readouterr().err


def test_nothing_to_play(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["--wsjtx", "--to", "127.0.0.1:2237", "--from", "991231_235959"])
    assert rc == 1 and "no received decodes" in capsys.readouterr().err
