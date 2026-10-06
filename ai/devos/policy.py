"""Permission policy: path scopes and tool/command classification (SRS §16).

Classification depends only on the tool, its canonical arguments and the policy
(PERM-002). Nothing here looks at model-provided explanations.
"""

from __future__ import annotations

import enum
import fnmatch
import os
import shlex
import shutil
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from . import paths as P


class Level(enum.IntEnum):
    SAFE = 0
    CONFIRM = 1
    BLOCKED = 2


@dataclass(frozen=True)
class Decision:
    level: Level
    reason: str

    def __or__(self, other: "Decision") -> "Decision":
        """The stricter of two decisions."""
        return other if other.level > self.level else self


SAFE = lambda reason: Decision(Level.SAFE, reason)  # noqa: E731
CONFIRM = lambda reason: Decision(Level.CONFIRM, reason)  # noqa: E731
BLOCKED = lambda reason: Decision(Level.BLOCKED, reason)  # noqa: E731


@dataclass(frozen=True)
class SafeRule:
    program: str
    subcommand: str | None = None
    forbid: tuple[str, ...] = ()
    flags_only: tuple[str, ...] | None = None

    def matches(self, argv: list[str]) -> bool:
        args = argv[1:]
        if self.subcommand is not None:
            if not args or args[0] != self.subcommand:
                return False
            args = args[1:]
        for a in args:
            for f in self.forbid:
                if a == f or a.startswith(f + "=") or (len(f) == 2 and f.startswith("-") and not f.startswith("--")
                                                       and a.startswith("-") and not a.startswith("--") and f[1] in a[1:]):
                    return False
        if self.flags_only is not None and any(a not in self.flags_only for a in args):
            return False
        return True


@dataclass
class Policy:
    limits: dict = field(default_factory=dict)
    denied: list[str] = field(default_factory=list)
    sensitive_names: list[str] = field(default_factory=list)
    protected: list[str] = field(default_factory=list)
    sandbox_cache_dirs: list[str] = field(default_factory=list)
    sandbox_env: list[str] = field(default_factory=list)
    shells: frozenset[str] = frozenset()
    wrappers: frozenset[str] = frozenset()
    blocked: frozenset[str] = frozenset()
    blocked_prefixes: tuple[str, ...] = ()
    safe_rules: list[SafeRule] = field(default_factory=list)

    # ---------------------------------------------------------------- loading
    @classmethod
    def load(cls, default: Path, admin: Path | None = None, user: Path | None = None) -> "Policy":
        data = tomllib.loads(default.read_text())
        if admin and admin.is_file():
            data = _merge(data, tomllib.loads(admin.read_text()))
        policy = cls.from_dict(data)
        if user and user.is_file():
            policy = policy.tightened(tomllib.loads(user.read_text()))
        return policy

    @classmethod
    def from_dict(cls, d: dict) -> "Policy":
        p, c = d.get("paths", {}), d.get("commands", {})
        return cls(
            limits=dict(d.get("limits", {})),
            denied=list(p.get("denied", [])),
            sensitive_names=list(p.get("sensitive_names", [])),
            protected=list(p.get("protected", [])),
            sandbox_cache_dirs=list(p.get("sandbox_cache_dirs", [])),
            sandbox_env=list(p.get("sandbox_env", [])),
            shells=frozenset(c.get("shells", [])),
            wrappers=frozenset(c.get("wrappers", [])),
            blocked=frozenset(c.get("blocked", [])),
            blocked_prefixes=tuple(c.get("blocked_prefixes", [])),
            safe_rules=[SafeRule(r["program"], r.get("subcommand"), tuple(r.get("forbid", [])),
                                 tuple(r["flags_only"]) if "flags_only" in r else None)
                        for r in c.get("safe", [])],
        )

    def tightened(self, user: dict) -> "Policy":
        """Apply a user policy that may only make things stricter (PERM-006)."""
        p, c, lim = user.get("paths", {}), user.get("commands", {}), user.get("limits", {})
        limits = dict(self.limits)
        for k, v in lim.items():
            if k in limits and isinstance(v, int) and 0 < v < limits[k]:
                limits[k] = v
        allowed = {(r.get("program"), r.get("subcommand")) for r in c.get("safe", [])} if "safe" in c else None
        return Policy(
            limits=limits,
            denied=self.denied + [x for x in p.get("denied", []) if x not in self.denied],
            sensitive_names=self.sensitive_names + list(p.get("sensitive_names", [])),
            protected=self.protected + list(p.get("protected", [])),
            sandbox_cache_dirs=[d for d in self.sandbox_cache_dirs
                                if d not in set(p.get("remove_sandbox_cache_dirs", []))],
            sandbox_env=self.sandbox_env,
            shells=self.shells,
            wrappers=self.wrappers,
            blocked=self.blocked | frozenset(c.get("blocked", [])),
            blocked_prefixes=self.blocked_prefixes + tuple(c.get("blocked_prefixes", [])),
            # A user "safe" list can only remove rules, never add them.
            safe_rules=[r for r in self.safe_rules
                        if allowed is None or (r.program, r.subcommand) in allowed],
        )

    def limit(self, name: str) -> int:
        return int(self.limits[name])

    # ------------------------------------------------------------------ paths
    def denied_paths(self) -> list[Path]:
        return [P.expand(x) for x in self.denied]

    def protected_paths(self) -> list[Path]:
        return [P.expand(x) for x in self.protected]

    def is_denied(self, path: Path) -> bool:
        return any(P.is_within(path, d) for d in self.denied_paths())

    def is_protected(self, path: Path) -> bool:
        return any(P.is_within(path, d) for d in self.protected_paths())

    def is_sensitive(self, path: Path) -> bool:
        return any(fnmatch.fnmatch(path.name, pat) for pat in self.sensitive_names)

    def scope(self, path: Path, workspace: Path) -> str:
        """'denied' | 'workspace' | 'home' | 'system' for a canonical path."""
        if self.is_denied(path):
            return "denied"
        if P.is_within(path, workspace):
            return "workspace"
        if P.is_within(path, P.home()):
            return "home"
        return "system"

    def classify_read(self, path: Path, workspace: Path) -> Decision:
        scope = self.scope(path, workspace)
        if scope == "denied":
            return BLOCKED(f"{path} is a protected location (credentials or DevOS data)")
        if scope == "workspace":
            if self.is_sensitive(path):
                return CONFIRM(f"{path.name} may contain secrets; its content will be sent to the AI provider")
            return SAFE("read inside workspace")
        return CONFIRM(f"read outside the workspace: {path}")

    def classify_write(self, path: Path, workspace: Path) -> Decision:
        scope = self.scope(path, workspace)
        if scope == "denied" or self.is_protected(path):
            return BLOCKED(f"{path} is protected and cannot be modified by the agent")
        if scope == "workspace":
            return CONFIRM("modify a file in the workspace")
        return BLOCKED(f"writing outside the workspace is not allowed: {path}")

    def check_workspace(self, workspace: Path) -> str | None:
        """Return an error message if `workspace` is not acceptable."""
        home = P.home()
        if not workspace.is_dir():
            return f"{workspace} is not a directory"
        if workspace == Path("/") or P.is_within(home, workspace):
            return "the workspace cannot be / or your home directory (or one of its parents)"
        if self.is_denied(workspace) or any(P.is_within(d, workspace) for d in self.denied_paths()):
            return "the workspace cannot contain or be inside a protected location"
        for sysdir in ("/usr", "/etc", "/boot", "/proc", "/sys", "/dev", "/run", "/var", "/opt", "/srv"):
            if P.is_within(workspace, Path(sysdir)):
                return f"the workspace cannot be inside {sysdir}"
        return None

    # --------------------------------------------------------------- commands
    def classify_command(self, argv: list[str], cwd: Path, workspace: Path, network: bool) -> Decision:
        if not argv or not all(isinstance(a, str) for a in argv) or any("\0" in a for a in argv):
            return BLOCKED("invalid command")
        decision = self._classify_argv(argv, cwd, workspace, depth=0)
        if network:
            decision |= CONFIRM("network access requested")
        if decision.level == Level.SAFE and not P.is_within(cwd, workspace):
            decision = CONFIRM(f"runs outside the workspace in {cwd}")
        return decision

    def _program(self, arg0: str) -> tuple[str, bool]:
        """(basename, resolved_from_path). Paths under system bin dirs count as PATH lookups."""
        if "/" not in arg0:
            return arg0, True
        p = Path(arg0)
        return p.name, str(p.parent) in ("/usr/bin", "/bin", "/usr/sbin", "/sbin", "/usr/local/bin")

    def _is_blocked_program(self, name: str) -> bool:
        return name in self.blocked or name.startswith(self.blocked_prefixes)

    def _classify_argv(self, argv: list[str], cwd: Path, workspace: Path, depth: int) -> Decision:
        if depth > 4:
            return CONFIRM("deeply nested command")
        name, from_path = self._program(argv[0])
        args = argv[1:]

        # Paths mentioned anywhere: denied locations are always blocked.
        path_decision = self._classify_path_args(args, cwd, workspace)
        if path_decision.level == Level.BLOCKED:
            return path_decision

        if self._is_blocked_program(name):
            return BLOCKED(f"'{name}' is not allowed for the agent (privileged or destructive)")

        if name == "systemctl":
            if "--user" not in args:
                return BLOCKED("system services cannot be managed by the agent")
            return CONFIRM("manage a user service")
        if name == "makepkg" and any(a in ("-i", "--install") or (a.startswith("-") and not a.startswith("--")
                                                                    and "i" in a[1:]) for a in args):
            return BLOCKED("installing packages goes through install_package")
        if name == "chmod" and _sets_special_bits(args):
            return BLOCKED("setting setuid/setgid bits is not allowed")
        if name == "rm" and _is_recursive_rm(args):
            for target in _positional(args):
                t = P.canonical(target, cwd)
                if t in (Path("/"), P.home(), workspace) or P.is_within(P.home(), t):
                    return BLOCKED(f"recursive delete of {t} is not allowed")

        if name in self.shells:
            script = _shell_script(args)
            if script is not None:
                inner = self._classify_script(script, cwd, workspace, depth)
                return inner | CONFIRM("runs a shell script")
            return CONFIRM(f"starts a {name} shell")

        if name in self.wrappers:
            inner = _unwrap(name, args)
            if inner:
                return self._classify_argv(inner, cwd, workspace, depth + 1) | CONFIRM(f"runs a command through {name}")
            return CONFIRM(f"{name} without a command")

        if from_path and args == ["--version"]:
            return SAFE("version query") | path_decision

        if from_path:
            for rule in self.safe_rules:
                if rule.program == name and rule.matches(argv):
                    return SAFE("allowlisted read-only command") | path_decision
        return CONFIRM("command is not on the read-only allowlist")

    def _classify_path_args(self, args: list[str], cwd: Path, workspace: Path) -> Decision:
        decision = SAFE("no paths outside the workspace")
        for a in args:
            for candidate in _path_candidates(a):
                path = P.canonical(candidate, cwd)
                if self.is_denied(path):
                    return BLOCKED(f"refers to a protected location: {path}")
                if not P.is_within(path, workspace):
                    decision |= CONFIRM(f"refers to a path outside the workspace: {path}")
        return decision

    def _classify_script(self, script: str, cwd: Path, workspace: Path, depth: int) -> Decision:
        """Best effort: block scripts that mention blocked programs or denied paths."""
        try:
            tokens = shlex.split(script, comments=True)
        except ValueError:
            tokens = script.split()
        decision = CONFIRM("shell script")
        command_start = True
        for tok in tokens:
            for piece in _split_operators(tok):
                if piece in (";", "&&", "||", "|", "&", "(", ")", "{", "}", "!", "then", "do", "else", "$("):
                    command_start = True
                    continue
                name, _ = self._program(piece.lstrip("($`"))
                if command_start and "=" not in piece and self._is_blocked_program(name):
                    return BLOCKED(f"script runs '{name}', which is not allowed for the agent")
                for candidate in _path_candidates(piece):
                    if self.is_denied(P.canonical(candidate, cwd)):
                        return BLOCKED(f"script refers to a protected location: {candidate}")
                command_start = name in self.wrappers
        return decision


# ---------------------------------------------------------------------- helpers

def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def _positional(args: list[str]) -> list[str]:
    out, end = [], False
    for a in args:
        if end or not a.startswith("-") or a == "-":
            out.append(a)
        elif a == "--":
            end = True
    return out


def _is_recursive_rm(args: list[str]) -> bool:
    for a in args:
        if a in ("--recursive", "-R"):
            return True
        if a.startswith("-") and not a.startswith("--") and ("r" in a[1:] or "R" in a[1:]):
            return True
    return False


def _sets_special_bits(args: list[str]) -> bool:
    for a in _positional(args)[:1]:
        if a.isdigit() and len(a) == 4 and a[0] in "2467":
            return True
        if "s" in a and any(c in a for c in "+="):
            return True
    return False


def _shell_script(args: list[str]) -> str | None:
    for i, a in enumerate(args):
        if a == "-c" or (a.startswith("-") and not a.startswith("--") and "c" in a[1:]):
            return args[i + 1] if i + 1 < len(args) else ""
        if not a.startswith("-"):
            return None  # script file: content unknown, still CONFIRM
    return None


_WRAPPER_ARG_OPTS = {
    "timeout": {"-s", "--signal", "-k", "--kill-after"},
    "nice": {"-n", "--adjustment"},
    "ionice": {"-c", "-n", "-p", "--class", "--classdata"},
    "stdbuf": {"-i", "-o", "-e"},
    "env": {"-u", "--unset", "-C", "--chdir", "-S", "--split-string"},
    "xargs": {"-a", "-d", "-E", "-I", "-L", "-n", "-P", "-s", "--arg-file", "--delimiter", "--max-args"},
    "taskset": {"-c"},
    "flock": {"-w", "-E", "-c"},
    "strace": {"-e", "-o", "-p", "-s", "-u"},
}


def _unwrap(name: str, args: list[str]) -> list[str]:
    """The command a wrapper runs: skip the wrapper's options and operands."""
    opts_with_value = _WRAPPER_ARG_OPTS.get(name, set())
    i, took_cpu_list = 0, False
    while i < len(args):
        a = args[i]
        if a == "--":
            i += 1
            break
        if a.startswith("-") and a != "-":
            took_cpu_list |= name == "taskset" and a in ("-c", "--cpu-list")
            i += 2 if a in opts_with_value else 1
            continue
        if name == "env" and "=" in a:
            i += 1
            continue
        break
    # Operands that come before the command: timeout DURATION, flock FILE, taskset MASK.
    if name in ("timeout", "flock") or (name == "taskset" and not took_cpu_list):
        i += 1
    return args[i:]


def _split_operators(tok: str) -> list[str]:
    out, cur = [], ""
    for ch in tok:
        if ch in ";|&()":
            if cur:
                out.append(cur)
                cur = ""
            out.append(ch)
        else:
            cur += ch
    if cur:
        out.append(cur)
    return out


def _path_candidates(arg: str) -> list[str]:
    """Strings inside an argument that look like filesystem paths."""
    out = []
    for part in [arg] + ([arg.split("=", 1)[1]] if arg.startswith("-") and "=" in arg else []):
        if part.startswith(("/", "~", "./", "../")) or part in (".", "..") or "/" in part and not part.startswith("-"):
            if "://" in part:  # URLs are not paths
                continue
            out.append(part)
    return out


def which(program: str) -> str | None:
    return shutil.which(program, path=os.environ.get("PATH", "/usr/bin:/bin"))
