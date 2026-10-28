"""qso-graph-sim: replays what ham radio programs send on the network, for testing."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import Final

try:
    _pkg_version = version("qso-graph-sim")
except PackageNotFoundError:  # source tree without dist metadata
    _pkg_version = "0.0.0-dev"

# Read from the installed distribution, so pyproject.toml is the only place
# the version is written.
__version__: Final[str] = _pkg_version
