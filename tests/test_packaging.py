"""Conventions that drift unless a test holds them."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"

# The first releases that reject the compromised eMudhra intermediate CAs
# (2026-10). Raise these when an advisory moves them; never lower them.
PATCHED = {(3, 11): 18, (3, 12): 16, (3, 13): 18, (3, 14): 10, (3, 15): 2}
VERSION = re.compile(r"""python-version:\s*(\[[^\]]*\]|["']?[^"'\s#]+["']?)""")


def _requested_pythons() -> list[tuple[str, str]]:
    found = []
    for wf in sorted(WORKFLOWS.glob("*.yml")):
        for m in VERSION.finditer(wf.read_text()):
            for v in re.findall(r"[\w.${}\-]+", m.group(1)):
                if not v.startswith("$"):  # ${{ matrix.python-version }}
                    found.append((wf.name, v))
    return found


def test_workflows_ask_for_a_python_at_all() -> None:
    assert _requested_pythons(), "the pattern found no python-version: the test is broken"


def test_every_python_is_a_patch_version_past_the_advisory() -> None:
    """"3.12" means "any 3.12", which on ubuntu-latest was 3.12.3: unpatched."""
    for wf, v in _requested_pythons():
        m = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", v)
        assert m, f"{wf} asks for Python {v!r}; ask for an exact patch release"
        major, minor, patch = map(int, m.groups())
        floor = PATCHED.get((major, minor))
        assert floor is not None, f"{wf}: Python {v} is a line this test does not know"
        assert patch >= floor, f"{wf}: Python {v} is older than {major}.{minor}.{floor}"


def test_publish_upgrades_pip_before_using_it() -> None:
    """pip trusts its own vendored certifi too, so uv.lock cannot fix pip."""
    text = (WORKFLOWS / "publish.yml").read_text()
    for job in ("Install test dependencies", "pip install build"):
        before = text[: text.index(job)]
        assert 'pip install --upgrade "pip>=26.2.2"' in before[-600:], (
            f"publish.yml runs pip ({job}) without upgrading it first"
        )


def test_the_command_is_qg_sim_and_the_package_name_still_works() -> None:
    """QSO Graph's commands are qg-<word>, its packages full qso-graph-* names (KI7MT,
    2026-11-03). `uv tool install X` and `uvx X` look for a command called X, so the
    package name stays installed as the same command, and nothing else is."""
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    name, scripts = project["name"], project.get("scripts", {})
    assert name.startswith("qso-graph-"), f"{name} is not a qso-graph-* package"
    command = "qg-" + name.removeprefix("qso-graph-")
    assert command in scripts, f"{name} installs no command called {command}"
    assert name in scripts, f"{name} no longer installs {name}, which uvx {name} runs"
    assert scripts[name] == scripts[command], f"{name} and {command} run different code"
    extra = sorted(set(scripts) - {command, name})
    assert not extra, f"unexpected commands: {extra}"
