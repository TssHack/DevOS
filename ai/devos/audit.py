"""Append-only JSONL audit log (SRS §19.1).

Records what happened and who decided, never file contents or command output
(LOG-002). Every record is redacted before it is written (SEC-004).
"""

from __future__ import annotations

import datetime as dt
import json
import os
import threading
from pathlib import Path
from typing import Any, Iterator

from . import paths, redact

_UTC = dt.timezone.utc


class AuditLog:
    def __init__(self, directory: Path | None = None, retention_days: int = 30):
        self.dir = directory or paths.state_dir() / "audit"
        self.retention_days = retention_days
        self._lock = threading.Lock()

    def _file(self, when: dt.datetime) -> Path:
        return self.dir / f"{when:%Y-%m-%d}.jsonl"

    def write(self, event: str, **fields: Any) -> dict:
        now = dt.datetime.now(_UTC)
        record = {"ts": now.isoformat(timespec="seconds").replace("+00:00", "Z"), "event": event}
        record.update(redact.value({k: v for k, v in fields.items() if v is not None}))
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
        with self._lock:
            paths.ensure_private_dir(self.dir)
            fd = os.open(self._file(now), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            try:
                os.write(fd, line.encode())
            finally:
                os.close(fd)
        return record

    def tail(self, n: int = 50) -> list[dict]:
        out: list[dict] = []
        for f in sorted(self.dir.glob("*.jsonl"), reverse=True):
            lines = f.read_text().splitlines()
            out = [json.loads(x) for x in lines if x.strip()] + out
            if len(out) >= n:
                break
        return out[-n:]

    def records(self) -> Iterator[dict]:
        for f in sorted(self.dir.glob("*.jsonl")):
            for line in f.read_text().splitlines():
                if line.strip():
                    yield json.loads(line)

    def prune(self) -> int:
        """Delete day files older than the retention period (LOG-003)."""
        if not self.dir.is_dir():
            return 0
        cutoff = dt.datetime.now(_UTC).date() - dt.timedelta(days=self.retention_days)
        removed = 0
        for f in self.dir.glob("*.jsonl"):
            try:
                day = dt.date.fromisoformat(f.stem)
            except ValueError:
                continue
            if day < cutoff:
                f.unlink()
                removed += 1
        return removed

    def clear(self) -> None:
        for f in self.dir.glob("*.jsonl"):
            f.unlink()


def format_record(r: dict) -> str:
    """One human-readable line for `devos audit` (LOG-004)."""
    ts = r.get("ts", "")[11:19]
    ev = r.get("event", "?")
    if ev == "tool":
        args = r.get("args", {})
        shown = " ".join(args["argv"]) if "argv" in args else ", ".join(f"{k}={v}" for k, v in args.items())
        parts = [f"[{ts}] tool {r.get('tool')}: {shown}", f"level={r.get('level')}", f"decision={r.get('decision')}"]
        if r.get("by"):
            parts.append(f"by={r['by']}")
        if "exit" in r:
            parts.append(f"exit={r['exit']}")
        if "ms" in r:
            parts.append(f"{r['ms']}ms")
        return "  ".join(parts)
    rest = {k: v for k, v in r.items() if k not in ("ts", "event")}
    return f"[{ts}] {ev} " + " ".join(f"{k}={v}" for k, v in rest.items())
