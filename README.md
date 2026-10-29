# qso-graph-sim

[![PyPI](https://img.shields.io/pypi/v/qso-graph-sim)](https://pypi.org/project/qso-graph-sim/)
[![Python](https://img.shields.io/pypi/pyversions/qso-graph-sim)](https://pypi.org/project/qso-graph-sim/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

Replays what a ham radio program sends on the network, from its own log, so you can build and test whatever receives it without a radio, an antenna or the program itself.

We start with **WSJT-X**. Give it an `ALL.TXT`, the log WSJT-X keeps of every decode, and it sends those decodes over UDP exactly as WSJT-X does: Heartbeat, Status and Decode messages, one cycle every 15 seconds. Anything that listens to WSJT-X, such as [QSO Graph Desktop](https://github.com/qso-graph/qso-graph-desktop)'s Monitor, sees a live band.

It needs nothing but Python and [qso-graph-lib](https://github.com/qso-graph/qso-graph-lib), which `pip` installs with it: no audio and no radio.

## Install

```bash
uv tool install qso-graph-sim
```

Or `pipx install qso-graph-sim`. Either puts the `qso-graph-sim` command on your PATH, on Windows, Linux and macOS alike. From 0.1.0, the first release; to run the newest code instead, see [Development](#development).

## Quick start

Point it at the computer and port your receiver listens on. WSJT-X's own default port is 2237.

```bash
qso-graph-sim --wsjtx --to 192.168.1.50:2237
```

With no `--file` it plays a sample that comes with it: almost two busy minutes of 20 m FT8: 120 decodes in 7 cycles. To play your own log, give it WSJT-X's `ALL.TXT`:

| Platform | Where WSJT-X keeps `ALL.TXT` |
|---|---|
| Windows | `%LOCALAPPDATA%\WSJT-X\ALL.TXT` |
| Linux | `~/.local/share/WSJT-X/ALL.TXT` |
| macOS | `~/Library/Application Support/WSJT-X/ALL.TXT` |

```bash
qso-graph-sim --wsjtx --to 192.168.1.50:2237 --file ALL.TXT --from 260407_233000 --call KI7MT --grid DN13
```

It stops at the end of the log (or keeps going with `--loop`), or when you press Ctrl+C. Either way it sends Clear and Close, as WSJT-X does when it shuts down.

## What it sends

Per cycle, in the order WSJT-X sends them:

| Message | When |
|---|---|
| Heartbeat | every 15 seconds |
| Status | as decoding starts and as it ends, with the log's dial frequency and mode, and your `--call` and `--grid` |
| Decode | one per line of the log, stamped with the cycle it is played in, so the band looks live |
| Clear, Close | on the way out |

It also answers **Replay**, the message a receiver sends to ask for the decodes WSJT-X already has: every decode played so far, marked not new, then a Status. It listens only to the address it was pointed at, and only to messages for its own Id.

The protocol is WSJT-X's own, as described in [`Network/NetworkMessage.hpp`](https://github.com/WSJTX/wsjtx/blob/master/Network/NetworkMessage.hpp), schema 3, encoded by `qso_graph_lib.jt`, the same code jt-mcp decodes it with. A Tx line in the log is skipped: these are decodes, not your own transmissions.

## Options

```text
qso-graph-sim --wsjtx --to IP:PORT [--file PATH] [--from YYMMDD_HHMMSS]
              [--id NAME] [--call CALL] [--grid GRID] [--speed N] [--loop]
```

| Option | Meaning |
|---|---|
| `--wsjtx` | the program to play as. WSJT-X is the first; more follow |
| `--to IP:PORT` | the receiver's address. An IP address, not a host name |
| `--file PATH` | the log to play; the sample if left out |
| `--from YYMMDD_HHMMSS` | start at this time in the log |
| `--id NAME` | the instance name to send as; WSJT-X's default is `WSJT-X`. Run two with different names to look like two rigs |
| `--call`, `--grid` | your callsign and grid, sent in Status |
| `--speed N` | play N times faster than real time, for automated tests; more than 0, up to 1000 |
| `--loop` | start again at the end |

## Testing with WSJT-X itself

To test with the real program and still no radio, run WSJT-X with **Rig: None**, then use **Help → Download Samples** and **File → Open** to play a recording. WSJT-X decodes it and sends the same messages it sends on the air, marked as off air.

## Development

```bash
git clone https://github.com/qso-graph/qso-graph-sim.git
cd qso-graph-sim
uv sync --group dev
uv run pytest
```

## Part of QSO-Graph

This package is part of [qso-graph](https://github.com/qso-graph), tools for amateur radio. See [qso-graph.io](https://qso-graph.io) for documentation.

## License

[GPLv3](LICENSE)
