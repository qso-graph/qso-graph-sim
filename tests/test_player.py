"""Playing a log over a real UDP socket, to a receiver on this machine."""

from __future__ import annotations

import socket
import threading
from collections.abc import Iterator
from importlib.resources import files

import pytest
from qso_graph_lib.jt import alltxt, protocol

from qso_graph_sim.player import Player, Station

SAMPLE = files("qso_graph_lib.jt").joinpath("samples", "ALL-sample.TXT").read_text("utf-8")


@pytest.fixture
def receiver() -> Iterator[socket.socket]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    sock.settimeout(5)
    yield sock
    sock.close()


def _player(
    receiver: socket.socket, log: alltxt.Log, speed: float
) -> tuple[Player, socket.socket]:
    sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sender.bind(("127.0.0.1", 0))
    player = Player(
        sock=sender, target=receiver.getsockname(), log=log,
        station=Station(sender="WSJT-X", call="KI7MT", grid="DN13"),
        speed=speed, say=lambda _line: None, clock=lambda: 85_000.0,
    )
    return player, sender


def _until_close(receiver: socket.socket) -> list[protocol.Message]:
    got = []
    while True:
        data, _ = receiver.recvfrom(65_535)
        msg = protocol.parse(data)
        got.append(msg)
        if msg.kind == protocol.MessageType.CLOSE:
            return got


def test_the_sample_plays_as_wsjtx_would_send_it(receiver: socket.socket) -> None:
    log = alltxt.read(SAMPLE)
    player, sender = _player(receiver, log, speed=1000)
    with sender:
        player.run()
        got = _until_close(receiver)
    kinds = [m.kind for m in got]
    decodes = [m for m in got if m.kind == protocol.MessageType.DECODE]

    assert kinds[0] == protocol.MessageType.HEARTBEAT
    assert kinds[-2:] == [protocol.MessageType.CLEAR, protocol.MessageType.CLOSE]
    assert kinds.count(protocol.MessageType.HEARTBEAT) == len(log.cycles)
    assert kinds.count(protocol.MessageType.STATUS) == 2 * len(log.cycles)
    assert len(decodes) == 120
    assert all(m.sender == "WSJT-X" for m in got)
    assert all(d.fields["is_new"] and d.fields["mode"] == "~" for d in decodes)
    assert decodes[0].fields["message"] == log.cycles[0].decodes[0].message

    # Each cycle is stamped 15 s after the last, from the T/R period under way
    # (the clock says 85,000 s: 23:36:40, so the first cycle is 23:36:30).
    stamps = sorted({d.fields["ms_of_day"] for d in decodes})
    assert stamps == [(85_000 // 15 * 15 + 15 * i) * 1000 for i in range(len(log.cycles))]

    status = next(m for m in got if m.kind == protocol.MessageType.STATUS)
    assert status.fields["dial_hz"] == 14_074_000
    assert (status.fields["de_call"], status.fields["de_grid"]) == ("KI7MT", "DN13")


def test_replay_resends_the_window_as_not_new(receiver: socket.socket) -> None:
    log = alltxt.read(SAMPLE)
    log.cycles = log.cycles[:2]
    player, sender = _player(receiver, log, speed=15)   # one cycle a second
    with sender:
        thread = threading.Thread(target=player.run)
        thread.start()
        # Wait for the first cycle's closing Status, then ask for a replay.
        seen = 0
        while seen < 2:
            msg = protocol.parse(receiver.recvfrom(65_535)[0])
            seen += msg.kind == protocol.MessageType.STATUS
        receiver.sendto(protocol.replay("WSJT-X"), sender.getsockname())
        got = _until_close(receiver)
        thread.join(5)

    old = [m for m in got if m.kind == protocol.MessageType.DECODE and not m.fields["is_new"]]
    assert len(old) == len(log.cycles[0].decodes)
    after = got.index(old[-1]) + 1
    assert got[after].kind == protocol.MessageType.STATUS


def test_only_the_receiver_it_was_pointed_at_is_heard(receiver: socket.socket) -> None:
    player, sender = _player(receiver, alltxt.read(SAMPLE), speed=1)
    with sender:
        assert player.accepts("127.0.0.1")
        assert player.accepts("::ffff:127.0.0.1")
        assert not player.accepts("192.168.1.50")


def test_a_replay_for_another_instance_is_ignored(receiver: socket.socket) -> None:
    log = alltxt.read(SAMPLE)
    player, sender = _player(receiver, log, speed=1)
    with sender:
        player._handle(protocol.replay("WSJT-X - FT-991A"), "127.0.0.1")
        player._handle(b"not wsjt-x at all", "127.0.0.1")
        receiver.settimeout(0.2)
        with pytest.raises(TimeoutError):
            receiver.recvfrom(65_535)
