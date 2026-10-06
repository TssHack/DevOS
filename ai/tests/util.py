"""Shared test fixtures: an isolated $HOME with a workspace inside it."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parent.parent
os.environ["DEVOS_SOURCE_TREE"] = "1"


def _sandbox_works() -> bool:
    import subprocess
    try:
        return subprocess.run(["bwrap", "--ro-bind", "/", "/", "--unshare-net", "--die-with-parent", "true"],
                              capture_output=True, timeout=20).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


SANDBOX_OK = _sandbox_works()
# For tests that start real bubblewrap sandboxes (unavailable in some build chroots).
requires_sandbox = unittest.skipUnless(SANDBOX_OK, "bubblewrap cannot run here")


class TempHome(unittest.TestCase):
    """Each test gets HOME=<tmp>/home, a workspace <tmp>/home/proj, and XDG dirs inside."""

    def setUp(self):
        # Not under /tmp: sandboxes mount a private /tmp, which would hide test files.
        base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "devos-tests"
        base.mkdir(parents=True, exist_ok=True)
        self._tmp = Path(tempfile.mkdtemp(prefix="t-", dir=base)).resolve()
        self.home = self._tmp / "home"
        self.ws = self.home / "proj"
        self.ws.mkdir(parents=True)
        self._saved_env = dict(os.environ)
        os.environ.update({
            "HOME": str(self.home),
            "XDG_CONFIG_HOME": str(self.home / ".config"),
            "XDG_DATA_HOME": str(self.home / ".local/share"),
            "XDG_STATE_HOME": str(self.home / ".local/state"),
            "XDG_RUNTIME_DIR": str(self._tmp / "run"),
        })
        (self._tmp / "run").mkdir(mode=0o700)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._saved_env)
        shutil.rmtree(self._tmp, ignore_errors=True)

    def policy(self):
        from devos.policy import Policy
        return Policy.load(AI_ROOT / "policy" / "policy.toml")
