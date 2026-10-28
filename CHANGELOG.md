# Changelog

All notable changes to `qso-graph-sim` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **`qso-graph-sim --wsjtx`**: plays a WSJT-X `ALL.TXT` as WSJT-X's UDP messages
  (Heartbeat, Status, Decode, Clear, Close), one cycle every 15 seconds, and answers Replay.
- A sample log of 120 decodes from 20 m FT8, played when no `--file` is given.
- An encoder and decoder for WSJT-X's protocol, schema 3, written to `NetworkMessage.hpp`.
