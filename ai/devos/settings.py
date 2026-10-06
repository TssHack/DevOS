"""DevOS AI settings (SRS §21, SET-002).

Defaults ship in defaults.toml; the user's ~/.config/devos/ai.toml overrides
them. An invalid user file is reported and ignored, never fatal. Secrets are
never stored here.
"""

from __future__ import annotations

import os
import re
import tomllib
from pathlib import Path

from . import paths

USER_KEYS = {
    ("ai", "model"): str,
    ("ai", "runtime"): str,
    ("daemon", "idle_exit_minutes"): int,
    ("daemon", "audit_retention_days"): int,
}
RUNTIMES = ("native", "hermes")


class Settings:
    def __init__(self, data: dict, error: str | None = None, path: Path | None = None):
        self.data = data
        self.error = error
        self.path = path or paths.config_dir() / "ai.toml"

    @classmethod
    def load(cls) -> "Settings":
        defaults = tomllib.loads((paths.share_dir() / "defaults.toml").read_text())
        path = paths.config_dir() / "ai.toml"
        user, error = {}, None
        if path.is_file():
            try:
                user = tomllib.loads(path.read_text())
                for (sec, key), typ in USER_KEYS.items():
                    v = user.get(sec, {}).get(key)
                    if v is not None and not isinstance(v, typ):
                        raise ValueError(f"[{sec}] {key} must be {typ.__name__}")
                env = user.get("env", {})
                if not all(isinstance(k, str) and _ENV_NAME.fullmatch(k) and isinstance(v, str)
                           for k, v in env.items()):
                    raise ValueError("[env] must contain NAME = \"value\" pairs")
            except (tomllib.TOMLDecodeError, ValueError) as e:
                user, error = {}, f"{path}: {e} (using defaults)"
        merged = {sec: dict(vals) for sec, vals in defaults.items()}
        for sec, vals in user.items():
            merged.setdefault(sec, {}).update(vals)
        return cls(merged, error, path)

    def get(self, section: str, key: str, default=None):
        return self.data.get(section, {}).get(key, default)

    @property
    def model(self) -> str:
        return self.get("ai", "model")

    @property
    def runtime(self) -> str:
        return self.get("ai", "runtime", "native")

    @property
    def env(self) -> dict[str, str]:
        return dict(self.data.get("env", {}))

    def set(self, section: str, key: str, value) -> None:
        if section == "env":
            if not _ENV_NAME.fullmatch(key) or not isinstance(value, str):
                raise ValueError("invalid environment variable")
            if key in _RESERVED_ENV:
                raise ValueError(f"{key} is managed by DevOS")
        else:
            typ = USER_KEYS.get((section, key))
            if typ is None:
                raise ValueError(f"unknown setting {section}.{key}")
            if not isinstance(value, typ):
                raise ValueError(f"{section}.{key} must be {typ.__name__}")
            if (section, key) == ("ai", "runtime") and value not in RUNTIMES:
                raise ValueError(f"runtime must be one of {', '.join(RUNTIMES)}")
        user = tomllib.loads(self.path.read_text()) if self.path.is_file() else {}
        user.setdefault(section, {})[key] = value
        self._write(user)
        self.data.setdefault(section, {})[key] = value

    def unset_env(self, key: str) -> None:
        user = tomllib.loads(self.path.read_text()) if self.path.is_file() else {}
        user.get("env", {}).pop(key, None)
        self._write(user)
        self.data.get("env", {}).pop(key, None)

    def _write(self, user: dict) -> None:
        paths.ensure_private_dir(self.path.parent)
        lines = ["# DevOS AI settings. Secrets are never stored here.", ""]
        for sec, vals in user.items():
            lines.append(f"[{sec}]")
            for k, v in vals.items():
                lines.append(f"{k} = {_toml_value(v)}")
            lines.append("")
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text("\n".join(lines))
        os.replace(tmp, self.path)


_ENV_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_RESERVED_ENV = {"PATH", "HOME", "USER", "LOGNAME", "CI", "DEVOS_SANDBOX", "LD_PRELOAD", "LD_LIBRARY_PATH"}


def _toml_value(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    s = str(v).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{s}"'
