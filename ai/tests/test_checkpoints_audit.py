import json
import os
import subprocess

from util import TempHome

from devos import redact
from devos.audit import AuditLog
from devos.checkpoints import CheckpointStore


class CheckpointTest(TempHome):
    def test_file_edit_undo(self):
        f = self.ws / "a.txt"
        f.write_text("original")
        cp = CheckpointStore().open("t1", self.ws)
        cp.record(f)
        f.write_text("changed")
        cp.record(f)  # second record must not overwrite the original
        new = self.ws / "new.txt"
        cp.record(new)
        new.write_text("created")
        cp.finish()
        self.assertEqual(sorted(cp.changed_files()), sorted([str(f), str(new)]))
        r = CheckpointStore().get("t1").undo()
        self.assertEqual(r["status"], "ok")
        self.assertEqual(f.read_text(), "original")
        self.assertFalse(new.exists())

    def test_command_snapshot_in_git_repo(self):
        subprocess.run(["git", "init", "-q"], cwd=self.ws, check=True)
        (self.ws / ".gitignore").write_text("ignored.log\n")
        (self.ws / "tracked.py").write_text("v1")
        (self.ws / "ignored.log").write_text("log")
        cp = CheckpointStore().open("t2", self.ws)
        self.assertTrue(cp.record_workspace())
        # what a command might do:
        (self.ws / "tracked.py").write_text("v2")
        (self.ws / "generated.txt").write_text("gen")
        os.remove(self.ws / ".gitignore")
        cp.after_command()
        cp.finish()
        cp.undo()
        self.assertEqual((self.ws / "tracked.py").read_text(), "v1")
        self.assertFalse((self.ws / "generated.txt").exists())
        self.assertEqual((self.ws / ".gitignore").read_text(), "ignored.log\n")
        self.assertEqual((self.ws / "ignored.log").read_text(), "log")  # ignored files untouched

    def test_conflict_after_task(self):  # UNDO-004
        f = self.ws / "a.txt"
        f.write_text("1")
        cp = CheckpointStore().open("t3", self.ws)
        cp.record(f)
        f.write_text("2")
        cp.finish()
        f.write_text("3 - user edited later")
        r = cp.undo()
        self.assertEqual(r["status"], "conflict")
        self.assertEqual(f.read_text(), "3 - user edited later")
        self.assertEqual(cp.undo(force=True)["status"], "ok")
        self.assertEqual(f.read_text(), "1")

    def test_checkpoint_dir_private(self):
        cp = CheckpointStore().open("t4", self.ws)
        (self.ws / "x").write_text("x")
        cp.record(self.ws / "x")
        self.assertEqual(os.stat(cp.dir).st_mode & 0o777, 0o700)


class AuditTest(TempHome):
    def test_records_are_redacted_and_private(self):
        key = "AIza" + "B" * 35
        redact.register(key)
        log = AuditLog()
        log.write("tool", tool="execute_command",
                  args={"argv": ["curl", "-H", f"x-goog-api-key: {key}", "-d", "token=ghp_" + "a" * 36]},
                  level="CONFIRM", decision="approved", by="user", exit=0, ms=12)
        log.write("note", text="API_KEY=supersecretvalue123")
        raw = "".join(p.read_text() for p in log.dir.glob("*.jsonl"))
        self.assertNotIn(key, raw)
        self.assertNotIn("ghp_" + "a" * 36, raw)
        self.assertNotIn("supersecretvalue123", raw)
        self.assertIn("[REDACTED]", raw)
        f = next(log.dir.glob("*.jsonl"))
        self.assertEqual(os.stat(f).st_mode & 0o777, 0o600)
        recs = log.tail(10)
        self.assertEqual([r["event"] for r in recs], ["tool", "note"])
        json.dumps(recs)

    def test_redact_private_key_block(self):
        pem = "-----BEGIN OPENSSH PRIVATE KEY-----\nabc\n-----END OPENSSH PRIVATE KEY-----"
        self.assertEqual(redact.text(f"x {pem} y"), "x [REDACTED] y")
