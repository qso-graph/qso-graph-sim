"""Playing an ALL.TXT back as WSJT-X would have sent it.

One cycle every 15 seconds, at the real pace unless sped up for a test. Per
cycle: a Heartbeat (WSJT-X sends one every 15 seconds), a Status as decoding
starts, the cycle's Decodes, and a Status as it ends. The Status carries the
dial frequency, so a band change in the log shows there; WSJT-X does not send
Clear for a band change, because its Band Activity window keeps the earlier
decodes, so neither does this. On the way out it sends Clear then Close, as
WSJT-X does when it shuts down normally.

Decodes are stamped with the cycle they are played in, not the one they were
logged in, so a receiver sees a live band rather than one from last April.

It answers Replay the way WSJT-X does: every decode still in its window,
marked not new, then a Status. Datagrams from anywhere but the address it was
pointed at are ignored, and so is anything addressed to a different Id.
"""

from __future__ import annotations

import select
import socket
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace

from . import wsjtx
from .alltxt import Cycle, Log

CYCLE_SECONDS = 15


@dataclass
class Station:
    sender: str = "WSJT-X"
    call: str = ""
    grid: str = ""


@dataclass
class Player:
    sock: socket.socket
    target: tuple[str, int]
    log: Log
    station: Station = field(default_factory=Station)
    speed: float = 1.0
    loop: bool = False
    say: Callable[[str], None] = print
    clock: Callable[[], float] = time.time
    _window: list[wsjtx.Decode] = field(default_factory=list, init=False)
    _status: wsjtx.Status | None = field(default=None, init=False)
    _stop: bool = field(default=False, init=False)

    def stop(self) -> None:
        self._stop = True

    def _send(self, data: bytes) -> None:
        self.sock.sendto(data, self.target)

    def _send_status(self) -> None:
        if self._status is not None:
            self._send(wsjtx.status(self.station.sender, self._status))

    # ------------------------------------------------------------ incoming

    def accepts(self, address: str) -> bool:
        """Only the receiver this was pointed at may talk to it."""
        return address.removeprefix("::ffff:") == self.target[0]

    def _handle(self, data: bytes, address: str) -> None:
        if not self.accepts(address):
            return
        try:
            msg = wsjtx.parse(data)
        except ValueError:
            return
        if msg.sender != self.station.sender:
            return
        if msg.kind == wsjtx.MessageType.REPLAY:
            self.say(f"replay asked for: sending {len(self._window)} decodes")
            for d in self._window:
                self._send(wsjtx.decode(self.station.sender, replace(d, is_new=False)))
            self._send_status()
        # Reply, Halt Tx, Free Text, Close and the rest would act on a real
        # WSJT-X. A monitor never sends them, so there is nothing to do.

    def _wait(self, until: float) -> None:
        """Sleep until ``until`` (real time), answering anything that arrives."""
        while not self._stop:
            left = until - time.monotonic()
            if left <= 0:
                return
            ready, _, _ = select.select([self.sock], [], [], min(left, 0.5))
            if ready:
                try:
                    data, (address, *_rest) = self.sock.recvfrom(65_535)
                except OSError:
                    continue
                self._handle(data, address)

    # ------------------------------------------------------------ playback

    def _play(self, cycle: Cycle, played_at: float) -> None:
        ms_of_day = int((played_at % 86_400) * 1000)
        self._status = wsjtx.Status(
            dial_hz=cycle.dial_hz, mode=cycle.mode, de_call=self.station.call,
            de_grid=self.station.grid, decoding=True,
        )
        self._send(wsjtx.heartbeat(self.station.sender))
        self._send_status()
        for line in cycle.decodes:
            d = wsjtx.Decode(
                is_new=True, ms_of_day=ms_of_day, snr=line.snr, dt=line.dt, df=line.df,
                mode=wsjtx.mode_character(line.mode), message=line.message,
                low_confidence=line.low_confidence,
            )
            self._send(wsjtx.decode(self.station.sender, d))
            self._window.append(d)
        self._status = replace(self._status, decoding=False)
        self._send_status()

    def run(self) -> None:
        if not self.log.cycles:
            raise ValueError("nothing to play: no received decodes")
        # The first cycle is stamped with the T/R period now under way; each
        # one after it, 15 seconds later.
        first = self.clock() // CYCLE_SECONDS * CYCLE_SECONDS
        started = time.monotonic()
        n = 0
        try:
            while not self._stop:
                for cycle in self.log.cycles:
                    if self._stop:
                        break
                    played_at = first + n * CYCLE_SECONDS
                    self._play(cycle, played_at)
                    stamp = time.strftime("%H:%M:%S", time.gmtime(played_at))
                    self.say(
                        f"{stamp}  {cycle.dial_hz / 1e6:.3f} {cycle.mode}  "
                        f"{len(cycle.decodes):2d} decodes  (logged {cycle.stamp})"
                    )
                    n += 1
                    self._wait(started + n * CYCLE_SECONDS / self.speed)
                if not self.loop:
                    break
        finally:
            self._send(wsjtx.clear(self.station.sender))
            self._send(wsjtx.close(self.station.sender))
