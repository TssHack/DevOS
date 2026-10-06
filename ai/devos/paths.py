"""Path helpers and DevOS file locations (SRS §19.2)."""

from __future__ import annotations

import os
from pathlib import Path


def home() -> Path:
    return Path(os.environ.get("HOME") or os.path.expanduser("~")).resolve()


def expand(p: str) -> Path:
    """Expand ~ against $HOME and make absolute, without resolving symlinks."""
    if p == "~" or p.startswith("~/"):
        p = str(home()) + p[1:]
    return Path(os.path.abspath(p))


def canonical(p: str | os.PathLike, cwd: str | os.PathLike | None = None) -> Path:
    """Absolute path with symlinks resolved (TOOL-0A). Works for paths that do not exist yet."""
    s = os.fspath(p)
    if s == "~" or s.startswith("~/"):
        s = str(home()) + s[1:]
    if not os.path.isabs(s):
        s = os.path.join(os.fspath(cwd) if cwd is not None else os.getcwd(), s)
    return Path(os.path.realpath(s))


def is_within(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _xdg(var: str, default: str) -> Path:
    v = os.environ.get(var)
    return Path(v) if v and os.path.isabs(v) else home() / default


def config_dir() -> Path:
    return _xdg("XDG_CONFIG_HOME", ".config") / "devos"


def data_dir() -> Path:
    return _xdg("XDG_DATA_HOME", ".local/share") / "devos"


def state_dir() -> Path:
    return _xdg("XDG_STATE_HOME", ".local/state") / "devos"


def runtime_dir() -> Path:
    base = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    return Path(base) / "devos"


def ui_socket() -> Path:
    return runtime_dir() / "ui.sock"


def agent_socket_dir() -> Path:
    return runtime_dir() / "agent"


def share_dir() -> Path:
    """Installed read-only data (policy, defaults). Falls back to the source tree."""
    installed = Path("/usr/share/devos/ai")
    if installed.is_dir() and not os.environ.get("DEVOS_SOURCE_TREE"):
        return installed
    return Path(__file__).resolve().parent.parent / "policy"


def ensure_private_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(p, 0o700)
    return p
