# Changelog

All notable changes to `qso-graph-sim` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-10-29

### Security

- **CI and publishing run patched Pythons and pip** (eMudhra CA advisory, 2026-10). Workflows
  ask for exact patch releases (3.11.18, 3.12.16, 3.13.18) instead of "3.12", which accepted
  the runner's unpatched 3.12.3, and `publish.yml` upgrades pip to 26.2.2 or later before
  using it. A test fails any workflow that asks for a minor version or an older patch.

### Added

- **`qso-graph-sim --wsjtx`**: plays a WSJT-X `ALL.TXT` as WSJT-X's UDP messages
  (Heartbeat, Status, Decode, Clear, Close), one cycle every 15 seconds, and answers Replay.
- A sample log of 120 decodes from 20 m FT8, played when no `--file` is given.
- An encoder and decoder for WSJT-X's protocol, schema 3, written to `NetworkMessage.hpp`.
- A test that the command is the package name, and any other command is prefixed with it.

### Fixed

- The README matched to what the tool does: the sample is 120 decodes in 7 cycles, Clear and Close are sent on every exit,
  and the link to `NetworkMessage.hpp` points at WSJT-X's `master` branch. `--help` names the
  `--id` and `--speed` values `NAME` and `N`, as the README does.

