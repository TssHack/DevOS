"""Run agent-requested processes inside bubblewrap (SRS §16.4).

The sandbox sees `/` read-only, the workspace read-write, toolchain caches
read-write, and nothing of the user's runtime directory (no D-Bus, Secret
Service, Wayland, ssh-agent or gpg-agent). Protected paths are masked.
bwrap always sets no_new_privs, so setuid programs (sudo, ...) cannot escalate.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from . import paths as P
from .policy import Policy

BWRAP = "/usr/bin/bwrap"


@dataclass
class Result:
    exit_code: int | None
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool = False
    cancelled: bool = False
    truncated: bool = False
    limited: bool = True  # ran under a systemd scope with resource limits

    def as_dict(self) -> dict:
        d = {"exit_code": self.exit_code, "stdout": self.stdout, "stderr": self.stderr,
             "duration_ms": self.duration_ms}
        if self.timed_out:
            d["timed_out"] = True
        if self.cancelled:
            d["cancelled"] = True
        if self.truncated:
            d["output_truncated"] = True
        return d


@dataclass
class Spec:
    argv: list[str]
    cwd: Path
    workspace: Path | None
    network: bool = False
    timeout: float = 300
    extra_env: dict[str, str] = field(default_factory=dict)
    # Extra read-write binds, e.g. the agent socket dir for the runtime sandbox.
    binds: list[Path] = field(default_factory=list)
    ro_binds: list[Path] = field(default_factory=list)
    hide_home: bool = False


def available() -> bool:
    return os.access(BWRAP, os.X_OK)


@lru_cache(maxsize=1)
def _systemd_scope_works() -> bool:
    if not shutil.which("systemd-run"):
        return False
    try:
        r = subprocess.run(["systemd-run", "--user", "--scope", "--quiet", "--collect", "true"],
                           capture_output=True, timeout=10)
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _prepare_cache_dirs(policy: Policy) -> list[Path]:
    """Existing (or safely creatable) cache dirs to bind read-write."""
    home = P.home()
    out = []
    for raw in policy.sandbox_cache_dirs:
        d = P.expand(raw)
        if not d.exists() and (d.parent.is_dir() and (d.parent != home or d.name == ".cache")):
            try:
                d.mkdir(mode=0o700)
            except OSError:
                pass
        if d.is_dir() and not policy.is_denied(d):
            out.append(d)
    return out


def build_argv(spec: Spec, policy: Policy) -> list[str]:
    home = P.home()
    a = [BWRAP, "--die-with-parent", "--new-session", "--unshare-pid", "--unshare-ipc",
         "--unshare-uts", "--unshare-cgroup-try",
         "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc",
         "--tmpfs", "/tmp", "--tmpfs", "/var/tmp", "--tmpfs", "/run"]

    if spec.network:
        # /etc/resolv.conf usually points into /run (systemd-resolved, NetworkManager).
        resolv = Path(os.path.realpath("/etc/resolv.conf"))
        if P.is_within(resolv, Path("/run")) and resolv.parent.is_dir():
            a += ["--ro-bind", str(resolv.parent), str(resolv.parent)]
    else:
        a.append("--unshare-net")

    # The user's runtime dir is under /run normally; mask it wherever it is.
    rt = os.environ.get("XDG_RUNTIME_DIR")
    if rt and not P.is_within(Path(rt), Path("/run")) and Path(rt).is_dir():
        a += ["--tmpfs", rt]

    if spec.hide_home:
        a += ["--tmpfs", str(home)]
    else:
        for d in _prepare_cache_dirs(policy):
            a += ["--bind", str(d), str(d)]
    if spec.workspace is not None:
        a += ["--bind", str(spec.workspace), str(spec.workspace)]
    for b in spec.binds:
        a += ["--bind", str(b), str(b)]
    for b in spec.ro_binds:
        a += ["--ro-bind", str(b), str(b)]

    # Masks go last so they win over the binds above.
    if not spec.hide_home:
        for d in policy.denied_paths():
            if d.is_dir() and not d.is_symlink():
                a += ["--tmpfs", str(d)]
            elif d.exists():
                a += ["--ro-bind", "/dev/null", str(d)]

    env = {k: os.environ[k] for k in policy.sandbox_env if k in os.environ}
    env.setdefault("PATH", "/usr/local/bin:/usr/bin")
    env["HOME"] = str(home)
    env["CI"] = "1"
    env["DEVOS_SANDBOX"] = "1"
    env["npm_config_cache"] = str(home / ".cache/npm")
    env["GOMODCACHE"] = str(home / ".cache/go-mod")
    # No stale/cluttering bytecode caches from agent runs inside the workspace.
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.update(spec.extra_env)
    a.append("--clearenv")
    for k, v in env.items():
        a += ["--setenv", k, v]
    a += ["--chdir", str(spec.cwd), "--"]
    return a + list(spec.argv)


async def run(spec: Spec, policy: Policy, output_limit: int | None = None) -> Result:
    if not available():
        raise RuntimeError("bubblewrap is not installed")
    limit = output_limit or policy.limit("command_output_bytes")
    argv = build_argv(spec, policy)
    limited = _systemd_scope_works()
    if limited:
        argv = ["systemd-run", "--user", "--scope", "--quiet", "--collect",
                "-p", f"MemoryMax={policy.limit('memory_max_percent')}%",
                "-p", f"TasksMax={policy.limit('tasks_max')}", "--"] + argv

    start = time.monotonic()
    proc = await asyncio.create_subprocess_exec(
        *argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        start_new_session=True)
    out, err = bytearray(), bytearray()
    truncated = [False]

    async def pump(stream: asyncio.StreamReader, buf: bytearray):
        while chunk := await stream.read(65536):
            room = limit - len(buf)
            if room > 0:
                buf += chunk[:room]
            if len(chunk) > room:
                truncated[0] = True  # keep draining so the process does not block

    timed_out = cancelled = False
    pumps = asyncio.ensure_future(asyncio.gather(pump(proc.stdout, out), pump(proc.stderr, err)))
    try:
        await asyncio.wait_for(asyncio.shield(pumps), timeout=spec.timeout)
        await proc.wait()
    except asyncio.TimeoutError:
        timed_out = True
    except asyncio.CancelledError:
        cancelled = True
    finally:
        if proc.returncode is None:
            _kill(proc)
            await proc.wait()
        # The pipes close once the sandbox is gone; then the pumps finish.
        try:
            await asyncio.wait_for(pumps, timeout=5)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            pass
    result = Result(
        exit_code=proc.returncode if not (timed_out or cancelled) else None,
        stdout=out.decode(errors="replace"), stderr=err.decode(errors="replace"),
        duration_ms=int((time.monotonic() - start) * 1000),
        timed_out=timed_out, cancelled=cancelled, truncated=truncated[0], limited=limited)
    if cancelled:
        raise asyncio.CancelledError
    return result


def _kill(proc: asyncio.subprocess.Process) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
