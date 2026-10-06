"""Per-task checkpoints and undo (SRS §17).

A checkpoint stores the original state of every file a task changes, recorded
once, before the first change. `undo` restores those originals. Files changed
after the task ended are reported instead of silently overwritten (UNDO-004).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from . import paths as P

MAX_UNTRACKED_WORKSPACE = 200 * 1024 * 1024  # UNDO-001: copy limit for non-Git workspaces
SKIP_DIRS = {".git", "node_modules", "target", "__pycache__", ".venv", "venv", "dist", "build", ".cache"}


def _sha256(path: Path) -> str | None:
    if not path.is_file() or path.is_symlink():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def workspace_files(workspace: Path) -> list[Path] | None:
    """Files that make up the workspace: Git-tracked + untracked-not-ignored, or a
    full walk for non-Git directories. None if too large to snapshot."""
    if (workspace / ".git").exists():
        try:
            r = subprocess.run(["git", "-c", "core.fsmonitor=false", "ls-files", "-z", "-co", "--exclude-standard"],
                               cwd=workspace, capture_output=True, timeout=60, check=True)
            return [workspace / p for p in r.stdout.decode(errors="surrogateescape").split("\0") if p]
        except (OSError, subprocess.SubprocessError):
            pass
    files, total = [], 0
    for root, dirs, names in os.walk(workspace):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for n in names:
            p = Path(root) / n
            try:
                total += p.lstat().st_size
            except OSError:
                continue
            if total > MAX_UNTRACKED_WORKSPACE:
                return None
            files.append(p)
    return files


MAX_EXISTENCE_INDEX = 500_000


def existing_paths(workspace: Path) -> set[str] | None:
    """Every path present in the workspace (except .git internals), or None if huge.
    Used to tell files a command created from files that merely became visible."""
    out: set[str] = set()
    stack = [str(workspace)]
    while stack:
        d = stack.pop()
        try:
            with os.scandir(d) as it:
                for e in it:
                    out.add(e.path)
                    if e.is_dir(follow_symlinks=False) and e.name != ".git":
                        stack.append(e.path)
        except OSError:
            continue
        if len(out) > MAX_EXISTENCE_INDEX:
            return None
    return out


class Checkpoint:
    """Original file states for one task. Layout: <dir>/manifest.json + blobs/<n>."""

    def __init__(self, directory: Path, workspace: Path):
        self.dir = directory
        self.workspace = workspace
        self.manifest_path = directory / "manifest.json"
        if self.manifest_path.exists():
            m = json.loads(self.manifest_path.read_text())
            self.entries: dict[str, dict] = m["entries"]
            self.finished: dict[str, str | None] = m.get("finished", {})
            self.created = m["created"]
        else:
            self.entries, self.finished = {}, {}
            self.created = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

    def _save(self) -> None:
        P.ensure_private_dir(self.dir)
        tmp = self.manifest_path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"workspace": str(self.workspace), "created": self.created,
                                   "entries": self.entries, "finished": self.finished}))
        os.replace(tmp, self.manifest_path)

    def record(self, path: Path) -> None:
        """Remember `path`'s current state, unless already recorded in this task."""
        key = str(path)
        if key in self.entries:
            return
        P.ensure_private_dir(self.dir / "blobs")
        if path.is_symlink():
            entry = {"kind": "symlink", "target": os.readlink(path)}
        elif path.is_file():
            blob = self.dir / "blobs" / str(len(self.entries))
            shutil.copy2(path, blob)
            entry = {"kind": "file", "blob": blob.name, "mode": path.stat().st_mode & 0o7777}
        elif path.exists():
            entry = {"kind": "other"}  # directories etc.: not restored
        else:
            entry = {"kind": "absent"}
        self.entries[key] = entry
        self._save()

    def record_workspace(self) -> bool:
        """Before a command: record every workspace file. False if not possible (UNDO-005)."""
        files = workspace_files(self.workspace)
        if files is None:
            return False
        for f in files:
            self.record(f)
        self._existed = existing_paths(self.workspace)
        return True

    def after_command(self) -> None:
        """Files that a command created were absent before it. Files that only
        became visible (e.g. a .gitignore was removed) are left alone."""
        existed = getattr(self, "_existed", None)
        if existed is None:
            return  # unknown baseline: never mark anything for deletion
        for f in workspace_files(self.workspace) or []:
            if str(f) not in self.entries and str(f) not in existed:
                self.entries[str(f)] = {"kind": "absent"}
        self._save()

    def finish(self) -> None:
        """Remember the post-task state so undo can detect later edits (UNDO-004)."""
        self.finished = {k: _sha256(Path(k)) for k in self.entries}
        self._save()

    def changed_files(self) -> list[str]:
        return [k for k, e in self.entries.items() if _state_differs(Path(k), e, self.dir)]

    def conflicts(self) -> list[str]:
        """Files modified after the task finished."""
        return [k for k, h in self.finished.items() if _sha256(Path(k)) != h]

    def undo(self, force: bool = False) -> dict:
        conflicts = self.conflicts()
        if conflicts and not force:
            return {"status": "conflict", "files": conflicts}
        restored, removed = [], []
        for key, e in self.entries.items():
            path = Path(key)
            if e["kind"] == "file":
                if _sha256(path) != _sha256(self.dir / "blobs" / e["blob"]):
                    path.parent.mkdir(parents=True, exist_ok=True)
                    if path.is_symlink() or path.is_dir():
                        _remove(path)
                    shutil.copy2(self.dir / "blobs" / e["blob"], path)
                    os.chmod(path, e["mode"])
                    restored.append(key)
            elif e["kind"] == "symlink":
                if not path.is_symlink() or os.readlink(path) != e["target"]:
                    _remove(path)
                    os.symlink(e["target"], path)
                    restored.append(key)
            elif e["kind"] == "absent" and (path.exists() or path.is_symlink()):
                _remove(path)
                removed.append(key)
        return {"status": "ok", "restored": sorted(restored), "removed": sorted(removed)}


def _state_differs(path: Path, e: dict, cp_dir: Path) -> bool:
    if e["kind"] == "absent":
        return path.exists() or path.is_symlink()
    if e["kind"] == "file":
        return _sha256(path) != _sha256(cp_dir / "blobs" / e["blob"])
    if e["kind"] == "symlink":
        return not path.is_symlink() or os.readlink(path) != e["target"]
    return False


def _remove(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)


class CheckpointStore:
    def __init__(self, root: Path | None = None, max_age_days: int = 7, max_bytes: int = 2 << 30):
        self.root = root or P.state_dir() / "checkpoints"
        self.max_age = max_age_days * 86400
        self.max_bytes = max_bytes

    def open(self, task_id: str, workspace: Path) -> Checkpoint:
        return Checkpoint(self.root / task_id, workspace)

    def get(self, task_id: str) -> Checkpoint | None:
        d = self.root / task_id
        if not (d / "manifest.json").exists():
            return None
        return Checkpoint(d, Path(json.loads((d / "manifest.json").read_text())["workspace"]))

    def prune(self) -> None:
        """UNDO-003: drop checkpoints older than 7 days, then oldest first above 2 GiB."""
        if not self.root.is_dir():
            return
        now = time.time()
        dirs = sorted((d for d in self.root.iterdir() if d.is_dir()), key=lambda d: d.stat().st_mtime)
        sizes = {d: sum(f.stat().st_size for f in d.rglob("*") if f.is_file()) for d in dirs}
        total = sum(sizes.values())
        for d in dirs:
            if now - d.stat().st_mtime > self.max_age or total > self.max_bytes:
                total -= sizes[d]
                shutil.rmtree(d, ignore_errors=True)

    def clear(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)
