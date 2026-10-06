"""Local conversation storage (SRS AI-008, §19.2): SQLite, mode 0600."""

from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from pathlib import Path

from . import paths, redact

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY, title TEXT NOT NULL, mode TEXT NOT NULL CHECK (mode IN ('chat', 'agent')),
    workspace TEXT, created REAL NOT NULL, updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS messages (
    conv_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    seq INTEGER NOT NULL, body TEXT NOT NULL, PRIMARY KEY (conv_id, seq));
"""


class ConversationStore:
    def __init__(self, path: Path | None = None):
        self.path = path or paths.data_dir() / "conversations.db"
        paths.ensure_private_dir(self.path.parent)
        new = not self.path.exists()
        self.db = sqlite3.connect(self.path, isolation_level=None, check_same_thread=False)
        if new:
            os.chmod(self.path, 0o600)
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.execute("PRAGMA journal_mode = WAL")
        self.db.executescript(SCHEMA)

    def create(self, mode: str, workspace: str | None = None, title: str | None = None) -> dict:
        cid, now = uuid.uuid4().hex[:12], time.time()
        self.db.execute("INSERT INTO conversations VALUES (?,?,?,?,?,?)",
                        (cid, title or "New conversation", mode, workspace, now, now))
        return self.get(cid, with_messages=False)

    def get(self, cid: str, with_messages: bool = True) -> dict | None:
        row = self.db.execute("SELECT id,title,mode,workspace,created,updated FROM conversations WHERE id=?",
                              (cid,)).fetchone()
        if not row:
            return None
        conv = dict(zip(("id", "title", "mode", "workspace", "created", "updated"), row))
        if with_messages:
            conv["messages"] = self.messages(cid)
        return conv

    def list(self) -> list[dict]:
        rows = self.db.execute("SELECT id,title,mode,workspace,created,updated FROM conversations "
                               "ORDER BY updated DESC").fetchall()
        return [dict(zip(("id", "title", "mode", "workspace", "created", "updated"), r)) for r in rows]

    def messages(self, cid: str) -> list[dict]:
        return [json.loads(b) for (b,) in self.db.execute(
            "SELECT body FROM messages WHERE conv_id=? ORDER BY seq", (cid,))]

    def append(self, cid: str, message: dict) -> None:
        seq = self.db.execute("SELECT COALESCE(MAX(seq), -1) + 1 FROM messages WHERE conv_id=?", (cid,)).fetchone()[0]
        self.db.execute("INSERT INTO messages VALUES (?,?,?)", (cid, seq, json.dumps(redact.value(message))))
        self.db.execute("UPDATE conversations SET updated=? WHERE id=?", (time.time(), cid))
        if seq == 0 and message.get("role") == "user":
            title = " ".join(message.get("text", "").split())[:60] or "New conversation"
            self.db.execute("UPDATE conversations SET title=? WHERE id=? AND title='New conversation'", (title, cid))

    def rename(self, cid: str, title: str) -> None:
        self.db.execute("UPDATE conversations SET title=? WHERE id=?", (title[:200], cid))

    def set_mode(self, cid: str, mode: str, workspace: str | None) -> None:
        self.db.execute("UPDATE conversations SET mode=?, workspace=? WHERE id=?", (mode, workspace, cid))

    def delete(self, cid: str) -> None:
        self.db.execute("DELETE FROM conversations WHERE id=?", (cid,))

    def clear(self) -> None:
        self.db.execute("DELETE FROM conversations")
        self.db.execute("VACUUM")
