"""Tool registry and implementations (SRS §15).

Each tool: JSON Schema arguments (MCP-compatible, D-12), `prepare` which
canonicalizes arguments, classifies them against the policy and builds the
approval preview, and `execute`. Only devosd runs tools; processes run in the
bubblewrap sandbox.
"""

from __future__ import annotations

import difflib
import os
import platform
import re
import shutil
import signal
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

from . import paths as P
from . import sandbox
from .checkpoints import Checkpoint
from .policy import BLOCKED, CONFIRM, SAFE, Decision, Level, Policy

MAX_READ_BYTES = 512 * 1024
MAX_LIST_ENTRIES = 1000
PKG_HELPER = "/usr/lib/devos/devos-pkg-helper"
PKG_NAME = re.compile(r"^[a-z0-9@._+-]+$")
GIT_HARDENING = ["-c", "core.fsmonitor=false", "-c", "core.pager=cat", "-c", "diff.external=",
                 "-c", "core.hooksPath=/dev/null", "-c", "color.ui=false"]


class ToolError(Exception):
    pass


@dataclass
class Context:
    policy: Policy
    workspace: Path
    checkpoint: Checkpoint | None = None
    session_pids: set[int] = field(default_factory=set)
    env: dict[str, str] = field(default_factory=dict)  # SBX-003 workspace variables


@dataclass
class Prepared:
    """A canonicalized, classified request, ready for approval and execution."""
    tool: "Tool"
    args: dict
    decision: Decision
    preview: dict
    writes: bool = False              # needs a checkpoint before running
    undoable: bool = True

    async def execute(self, ctx: Context) -> dict:
        return await self.tool.run(self.args, ctx)


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    prepare_fn: Callable[[dict, Context], Prepared]
    run: Callable[[dict, Context], Awaitable[dict]]

    def prepare(self, args: dict, ctx: Context) -> Prepared:
        _validate(args, self.parameters)
        p = self.prepare_fn(args, ctx)
        p.tool = self
        return p

    def spec(self) -> dict:
        return {"name": self.name, "description": self.description, "inputSchema": self.parameters}


def _validate(args: Any, schema: dict) -> None:
    if not isinstance(args, dict):
        raise ToolError("arguments must be an object")
    props = schema.get("properties", {})
    for req in schema.get("required", []):
        if req not in args:
            raise ToolError(f"missing argument '{req}'")
    for k, v in args.items():
        if k not in props:
            raise ToolError(f"unknown argument '{k}'")
        t = props[k].get("type")
        ok = {"string": isinstance(v, str), "integer": isinstance(v, int) and not isinstance(v, bool),
              "boolean": isinstance(v, bool),
              "array": isinstance(v, list) and all(isinstance(x, str) for x in v)}.get(t, True)
        if not ok:
            raise ToolError(f"argument '{k}' must be of type {t}")


def _obj(props: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": props, "required": required}


S = {"type": "string"}
I = {"type": "integer"}
B = {"type": "boolean"}
A = {"type": "array", "items": {"type": "string"}}


def _path(ctx: Context, raw: str) -> Path:
    return P.canonical(raw, ctx.workspace)


def _rel(ctx: Context, p: Path) -> str:
    return str(p.relative_to(ctx.workspace)) if P.is_within(p, ctx.workspace) else str(p)


def _diff(old: str, new: str, name: str) -> str:
    lines = difflib.unified_diff(old.splitlines(True), new.splitlines(True), f"a/{name}", f"b/{name}")
    return "".join(lines)[:200_000]


async def _sandboxed(ctx: Context, argv: list[str], cwd: Path | None = None, network: bool = False,
                     timeout: float | None = None) -> dict:
    spec = sandbox.Spec(argv=argv, cwd=cwd or ctx.workspace, workspace=ctx.workspace, network=network,
                        timeout=timeout or ctx.policy.limit("command_timeout_default"), extra_env=ctx.env)
    result = await sandbox.run(spec, ctx.policy)
    return result.as_dict()


# ---------------------------------------------------------------- filesystem

def _prep_list(a, ctx):
    p = _path(ctx, a.get("path", "."))
    return Prepared(None, {"path": str(p), "depth": max(1, min(int(a.get("depth", 1)), 3))},
                    ctx.policy.classify_read(p, ctx.workspace), {"path": str(p)})


async def _run_list(a, ctx):
    root, depth = Path(a["path"]), a["depth"]
    if not root.is_dir():
        raise ToolError(f"not a directory: {root}")
    entries: list[str] = []

    def walk(d: Path, level: int):
        for e in sorted(os.scandir(d), key=lambda e: e.name):
            if len(entries) >= MAX_LIST_ENTRIES:
                return
            p = Path(e.path)
            if ctx.policy.is_denied(p):
                continue
            is_dir = e.is_dir(follow_symlinks=False)
            entries.append(str(p.relative_to(root)) + ("/" if is_dir else ""))
            if is_dir and level < depth and e.name not in (".git", "node_modules", "target", "__pycache__"):
                walk(p, level + 1)

    walk(root, 1)
    return {"path": str(root), "entries": entries, "truncated": len(entries) >= MAX_LIST_ENTRIES}


def _prep_read(a, ctx):
    p = _path(ctx, a["path"])
    return Prepared(None, {"path": str(p), "offset": max(0, a.get("offset", 0)),
                           "limit": max(1, min(a.get("limit", MAX_READ_BYTES), MAX_READ_BYTES))},
                    ctx.policy.classify_read(p, ctx.workspace), {"path": str(p)})


async def _run_read(a, ctx):
    p = Path(a["path"])
    if not p.is_file():
        raise ToolError(f"not a file: {p}")
    with p.open("rb") as f:
        f.seek(a["offset"])
        data = f.read(a["limit"] + 1)
    if b"\0" in data[:8192]:
        return {"path": str(p), "binary": True, "size": p.stat().st_size}
    more = len(data) > a["limit"]
    return {"path": str(p), "content": data[:a["limit"]].decode(errors="replace"), "size": p.stat().st_size,
            "truncated": more}


def _prep_search(a, ctx):
    p = _path(ctx, a.get("path", "."))
    args = {"pattern": a["pattern"], "path": str(p), "glob": a.get("glob")}
    return Prepared(None, args, ctx.policy.classify_read(p, ctx.workspace), dict(args))


async def _run_search(a, ctx):
    if shutil.which("rg"):
        argv = ["rg", "-n", "--no-heading", "--color=never", "--max-count=50", "--max-columns=300"]
        if a.get("glob"):
            argv += ["-g", a["glob"]]
        argv += ["-e", a["pattern"], "--", a["path"]]
    else:
        argv = ["grep", "-rnI", "-m", "50", "-e", a["pattern"], "--", a["path"]]
    r = await _sandboxed(ctx, argv, timeout=60)
    r["matches"] = r.pop("stdout")
    return r


def _prep_write(a, ctx):
    p = _path(ctx, a["path"])
    d = ctx.policy.classify_write(p, ctx.workspace)
    old = p.read_text(errors="replace") if p.is_file() else ""
    return Prepared(None, {"path": str(p), "content": a["content"]}, d,
                    {"path": str(p), "diff": _diff(old, a["content"], _rel(ctx, p)), "new_file": not p.exists()},
                    writes=True)


async def _run_write(a, ctx):
    p = Path(a["path"])
    if ctx.checkpoint:
        ctx.checkpoint.record(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(a["content"])
    return {"path": str(p), "bytes": len(a["content"].encode())}


def _prep_edit(a, ctx):
    p = _path(ctx, a["path"])
    d = ctx.policy.classify_write(p, ctx.workspace)
    if d.level == Level.BLOCKED:
        return Prepared(None, {"path": str(p)}, d, {"path": str(p)})
    if not p.is_file():
        raise ToolError(f"not a file: {p}")
    text = p.read_text()
    count = text.count(a["old"])
    if count != 1:
        raise ToolError(f"'old' must match exactly once in {p.name} (found {count} matches)")
    new = text.replace(a["old"], a["new"], 1)
    return Prepared(None, {"path": str(p), "content": new}, d,
                    {"path": str(p), "diff": _diff(text, new, _rel(ctx, p))}, writes=True)


def _prep_mkdir(a, ctx):
    p = _path(ctx, a["path"])
    return Prepared(None, {"path": str(p)}, ctx.policy.classify_write(p, ctx.workspace), {"path": str(p)})


async def _run_mkdir(a, ctx):
    Path(a["path"]).mkdir(parents=True, exist_ok=True)
    return {"path": a["path"], "created": True}


def _prep_delete(a, ctx):
    p = _path(ctx, a["path"])
    d = ctx.policy.classify_write(p, ctx.workspace)
    if p.is_dir() and not p.is_symlink():
        d = BLOCKED("deleting directories is not allowed; delete files individually")
    return Prepared(None, {"path": str(p)}, d, {"path": str(p)}, writes=True)


async def _run_delete(a, ctx):
    p = Path(a["path"])
    if ctx.checkpoint:
        ctx.checkpoint.record(p)
    p.unlink()
    return {"path": str(p), "deleted": True}


# ------------------------------------------------------------------ commands

def _prep_exec(a, ctx):
    argv = a["argv"]
    if not argv:
        raise ToolError("argv must not be empty")
    cwd = _path(ctx, a.get("cwd", "."))
    network = bool(a.get("network", False))
    tmax = ctx.policy.limit("command_timeout_max")
    timeout = max(1, min(int(a.get("timeout_s", ctx.policy.limit("command_timeout_default"))), tmax))
    d = ctx.policy.classify_command(argv, cwd, ctx.workspace, network)
    if not cwd.is_dir():
        raise ToolError(f"working directory does not exist: {cwd}")
    return Prepared(None, {"argv": argv, "cwd": str(cwd), "network": network, "timeout_s": timeout}, d,
                    {"argv": argv, "cwd": str(cwd), "network": network, "timeout_s": timeout},
                    writes=d.level != Level.SAFE)


async def _run_exec(a, ctx):
    argv = list(a["argv"])
    if argv[0] == "git":
        argv = ["git"] + GIT_HARDENING + argv[1:]
    cp = ctx.checkpoint
    if cp and a.get("_snapshot", True):
        cp.record_workspace()
    try:
        return await _sandboxed(ctx, argv, cwd=Path(a["cwd"]), network=a["network"], timeout=a["timeout_s"])
    finally:
        if cp:
            cp.after_command()


# ----------------------------------------------------------------------- git

def _git_safe(argv_tail: list[str]):
    def prep(a, ctx):
        argv = ["git"] + argv_tail(a) if callable(argv_tail) else ["git"] + argv_tail
        return Prepared(None, {"argv": argv}, SAFE("read-only git query"), {"argv": argv})
    return prep


async def _run_git_read(a, ctx):
    r = await _sandboxed(ctx, ["git"] + GIT_HARDENING + a["argv"][1:], timeout=60)
    return r


def _prep_git_write(build: Callable[[dict, Context], list[str]], reason: str):
    def prep(a, ctx):
        argv = build(a, ctx)
        for raw in a.get("paths", []):
            if not P.is_within(P.canonical(raw, ctx.workspace), ctx.workspace):
                return Prepared(None, {"argv": argv}, BLOCKED(f"path outside the workspace: {raw}"), {"argv": argv})
        return Prepared(None, {"argv": argv}, CONFIRM(reason), {"argv": argv}, writes=True)
    return prep


async def _run_git_write(a, ctx):
    if ctx.checkpoint:
        ctx.checkpoint.record_workspace()
    try:
        return await _sandboxed(ctx, a["argv"], timeout=120)
    finally:
        if ctx.checkpoint:
            ctx.checkpoint.after_command()


def _ref(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9._/\-]+", name) or name.startswith("-") or ".." in name:
        raise ToolError(f"invalid branch name: {name}")
    return name


# -------------------------------------------------------------------- system

def _prep_sys(a, ctx):
    return Prepared(None, {}, SAFE("system information"), {})


async def _run_system_info(a, ctx):
    u = platform.uname()
    info = {"os": _os_release(), "kernel": u.release, "machine": u.machine, "hostname": u.node,
            "cpus": os.cpu_count(), "python": platform.python_version()}
    try:
        info["uptime_s"] = int(float(Path("/proc/uptime").read_text().split()[0]))
        info["load"] = Path("/proc/loadavg").read_text().split()[:3]
    except OSError:
        pass
    return info


def _os_release() -> str:
    try:
        for line in Path("/etc/os-release").read_text().splitlines():
            if line.startswith("PRETTY_NAME="):
                return line.split("=", 1)[1].strip('"')
    except OSError:
        pass
    return platform.system()


async def _run_processes(a, ctx):
    procs = []
    uid = os.getuid()
    for d in Path("/proc").iterdir():
        if not d.name.isdigit():
            continue
        try:
            if d.stat().st_uid != uid:
                continue
            status = dict(line.split(":\t", 1) for line in (d / "status").read_text().splitlines() if ":\t" in line)
            # Names only: command lines can contain secrets.
            procs.append({"pid": int(d.name), "name": status.get("Name", "").strip(),
                          "rss_kb": int(status.get("VmRSS", "0 kB").split()[0])})
        except (OSError, ValueError):
            continue
    procs.sort(key=lambda p: -p["rss_kb"])
    return {"processes": procs[:100], "total": len(procs)}


async def _run_disk(a, ctx):
    out = []
    for mount in ("/", str(P.home()), str(ctx.workspace)):
        try:
            st = os.statvfs(mount)
        except OSError:
            continue
        out.append({"path": mount, "total_gb": round(st.f_blocks * st.f_frsize / 1e9, 1),
                    "free_gb": round(st.f_bavail * st.f_frsize / 1e9, 1)})
    return {"filesystems": out}


async def _run_memory(a, ctx):
    info = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        k, v = line.split(":", 1)
        if k in ("MemTotal", "MemAvailable", "SwapTotal", "SwapFree"):
            info[k] = int(v.split()[0]) // 1024
    return {"mb": info}


def _prep_kill(a, ctx):
    pid, sig = a["pid"], a.get("signal", "TERM")
    if sig not in ("TERM", "INT", "KILL", "HUP"):
        raise ToolError("signal must be TERM, INT, KILL or HUP")
    d = CONFIRM("stop a process") if pid in ctx.session_pids else \
        BLOCKED("only processes started in this agent session can be stopped")
    return Prepared(None, {"pid": pid, "signal": sig}, d, {"pid": pid, "signal": sig})


async def _run_kill(a, ctx):
    os.kill(a["pid"], getattr(signal, "SIG" + a["signal"]))
    return {"pid": a["pid"], "signal": a["signal"]}


# ------------------------------------------------------------------ packages

def _prep_pkg_search(a, ctx):
    return Prepared(None, {"query": a["query"]}, SAFE("package search"), {"query": a["query"]})


async def _run_pkg_search(a, ctx):
    r = await _sandboxed(ctx, ["pacman", "-Ss", "--", a["query"]], cwd=Path("/"), timeout=60)
    return {"results": r["stdout"][:20000], "exit_code": r["exit_code"]}


def _prep_pkg(action: str):
    def prep(a, ctx):
        names = a["names"]
        if not names or len(names) > 50 or not all(PKG_NAME.fullmatch(n) for n in names):
            raise ToolError("invalid package names")
        return Prepared(None, {"action": action, "names": names},
                        CONFIRM(f"{action} system packages (administrator password required)"),
                        {"action": action, "packages": names}, undoable=False)
    return prep


async def _run_pkg(a, ctx):
    import asyncio
    if not os.access(PKG_HELPER, os.X_OK):
        raise ToolError("devos-pkg-helper is not installed")
    # Not sandboxed: pkexec needs the polkit agent; the helper validates everything again.
    proc = await asyncio.create_subprocess_exec("pkexec", PKG_HELPER, a["action"], *a["names"],
                                                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    out, err = await proc.communicate()
    return {"exit_code": proc.returncode, "stdout": out.decode(errors="replace")[-20000:],
            "stderr": err.decode(errors="replace")[-5000:]}


# ------------------------------------------------------------------ registry

def _t(name, desc, params, prep, run) -> Tool:
    return Tool(name, desc, params, prep, run)


TOOLS: dict[str, Tool] = {t.name: t for t in [
    _t("list_directory", "List files in a directory of the workspace (depth 1-3).",
       _obj({"path": S, "depth": I}, []), _prep_list, _run_list),
    _t("read_file", "Read a text file. Paths are relative to the workspace.",
       _obj({"path": S, "offset": I, "limit": I}, ["path"]), _prep_read, _run_read),
    _t("search_files", "Search file contents with a regular expression (ripgrep).",
       _obj({"pattern": S, "path": S, "glob": S}, ["pattern"]), _prep_search, _run_search),
    _t("write_file", "Create or overwrite a file in the workspace. Requires user approval.",
       _obj({"path": S, "content": S}, ["path", "content"]), _prep_write, _run_write),
    _t("edit_file", "Replace one exact occurrence of 'old' with 'new' in a file. Requires user approval.",
       _obj({"path": S, "old": S, "new": S}, ["path", "old", "new"]), _prep_edit, _run_write),
    _t("create_directory", "Create a directory in the workspace. Requires user approval.",
       _obj({"path": S}, ["path"]), _prep_mkdir, _run_mkdir),
    _t("delete_file", "Delete a single file in the workspace. Requires user approval.",
       _obj({"path": S}, ["path"]), _prep_delete, _run_delete),
    _t("execute_command",
       "Run a program (argv list, no shell) in a sandbox inside the workspace. Read-only commands like "
       "ls, cat, rg, git status run directly; others (builds, tests, installs) need user approval. "
       "Network is off unless network=true.",
       _obj({"argv": A, "cwd": S, "timeout_s": I, "network": B}, ["argv"]), _prep_exec, _run_exec),
    _t("git_status", "Show git status.", _obj({}, []), _git_safe(["status", "--short", "--branch"]), _run_git_read),
    _t("git_diff", "Show git diff (optionally staged or for one path).", _obj({"staged": B, "path": S}, []),
       _git_safe(lambda a: ["diff"] + (["--staged"] if a.get("staged") else []) +
                 (["--", a["path"]] if a.get("path") else [])), _run_git_read),
    _t("git_log", "Show recent commits.", _obj({"count": I}, []),
       _git_safe(lambda a: ["log", "--oneline", "--decorate", f"-n{max(1, min(a.get('count', 20), 200))}"]),
       _run_git_read),
    _t("git_branch", "List branches.", _obj({}, []), _git_safe(["branch", "-a", "-vv"]), _run_git_read),
    _t("git_add", "Stage files. Requires user approval.", _obj({"paths": A}, ["paths"]),
       _prep_git_write(lambda a, c: ["git", "add", "--"] + a["paths"], "stage changes"), _run_git_write),
    _t("git_commit", "Commit staged changes. Requires user approval.", _obj({"message": S}, ["message"]),
       _prep_git_write(lambda a, c: ["git", "commit", "-m", a["message"]], "create a commit"), _run_git_write),
    _t("git_checkout", "Switch to a branch. Requires user approval.", _obj({"name": S}, ["name"]),
       _prep_git_write(lambda a, c: ["git", "checkout", _ref(a["name"])], "switch branch"), _run_git_write),
    _t("git_branch_create", "Create and switch to a new branch. Requires user approval.", _obj({"name": S}, ["name"]),
       _prep_git_write(lambda a, c: ["git", "checkout", "-b", _ref(a["name"])], "create a branch"), _run_git_write),
    _t("system_info", "Operating system, kernel, CPU and load.", _obj({}, []), _prep_sys, _run_system_info),
    _t("process_list", "Your processes by memory use (names only).", _obj({}, []), _prep_sys, _run_processes),
    _t("disk_usage", "Free space on / , home and the workspace.", _obj({}, []), _prep_sys, _run_disk),
    _t("memory_usage", "RAM and swap usage.", _obj({}, []), _prep_sys, _run_memory),
    _t("kill_process", "Stop a process started in this agent session. Requires user approval.",
       _obj({"pid": I, "signal": S}, ["pid"]), _prep_kill, _run_kill),
    _t("search_package", "Search Arch Linux packages.", _obj({"query": S}, ["query"]), _prep_pkg_search,
       _run_pkg_search),
    _t("install_package", "Install system packages. Requires user approval and the administrator password.",
       _obj({"names": A}, ["names"]), _prep_pkg("install"), _run_pkg),
    _t("remove_package", "Remove system packages. Requires user approval and the administrator password.",
       _obj({"names": A}, ["names"]), _prep_pkg("remove"), _run_pkg),
]}


def get(name: str) -> Tool:
    if name not in TOOLS:
        raise ToolError(f"unknown tool '{name}'")
    return TOOLS[name]


def specs() -> list[dict]:
    return [t.spec() for t in TOOLS.values()]
