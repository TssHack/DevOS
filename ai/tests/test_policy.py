import os
import shlex
from pathlib import Path

from util import AI_ROOT, TempHome

from devos.policy import Level, Policy


def load_corpus():
    cases = []
    for lineno, line in enumerate((AI_ROOT / "policy" / "corpus.txt").read_text().splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        level, net, command = line.split(None, 2)
        cases.append((lineno, Level[level], net == "net", command))
    return cases


class CorpusTest(TempHome):
    def test_corpus_size(self):
        self.assertGreaterEqual(len(load_corpus()), 200)  # PERM-014

    def test_corpus(self):
        policy = self.policy()
        failures = []
        for lineno, expected, net, command in load_corpus():
            argv = shlex.split(command.replace("{ws}", str(self.ws)))
            got = policy.classify_command(argv, self.ws, self.ws, net)
            if got.level != expected:
                failures.append(f"line {lineno}: {command!r}: expected {expected.name}, got {got.level.name} ({got.reason})")
        self.assertEqual(failures, [], "\n" + "\n".join(failures))


class PathTest(TempHome):
    def test_scopes(self):
        p = self.policy()
        self.assertEqual(p.classify_read(self.ws / "a.py", self.ws).level, Level.SAFE)
        self.assertEqual(p.classify_read(self.ws / ".env", self.ws).level, Level.CONFIRM)
        self.assertEqual(p.classify_read(self.ws / "server.pem", self.ws).level, Level.CONFIRM)
        self.assertEqual(p.classify_read(self.home / "notes.txt", self.ws).level, Level.CONFIRM)
        self.assertEqual(p.classify_read(Path("/etc/hosts"), self.ws).level, Level.CONFIRM)
        self.assertEqual(p.classify_read(self.home / ".ssh/id_ed25519", self.ws).level, Level.BLOCKED)
        self.assertEqual(p.classify_read(Path("/etc/shadow"), self.ws).level, Level.BLOCKED)

        self.assertEqual(p.classify_write(self.ws / "a.py", self.ws).level, Level.CONFIRM)
        self.assertEqual(p.classify_write(self.home / "a.py", self.ws).level, Level.BLOCKED)
        self.assertEqual(p.classify_write(Path("/etc/hosts"), self.ws).level, Level.BLOCKED)
        self.assertEqual(p.classify_write(self.home / ".bashrc", self.ws).level, Level.BLOCKED)
        self.assertEqual(p.classify_write(self.home / ".config/hypr/hyprland.conf", self.ws).level, Level.BLOCKED)

    def test_symlink_out_of_workspace_is_outside(self):  # PERM-021
        from devos import paths
        (self.home / ".ssh").mkdir()
        (self.home / ".ssh/id_rsa").write_text("k")
        os.symlink(self.home / ".ssh", self.ws / "innocent")
        p = self.policy()
        target = paths.canonical("innocent/id_rsa", self.ws)
        self.assertEqual(p.classify_read(target, self.ws).level, Level.BLOCKED)
        argv = ["cat", "innocent/id_rsa"]
        self.assertEqual(p.classify_command(argv, self.ws, self.ws, False).level, Level.BLOCKED)

    def test_workspace_validation(self):
        p = self.policy()
        self.assertIsNone(p.check_workspace(self.ws))
        self.assertIsNotNone(p.check_workspace(self.home))
        self.assertIsNotNone(p.check_workspace(Path("/")))
        self.assertIsNotNone(p.check_workspace(Path("/usr")))
        (self.home / ".ssh").mkdir()
        self.assertIsNotNone(p.check_workspace(self.home / ".ssh"))
        self.assertIsNotNone(p.check_workspace(self.ws / "missing"))

    def test_cwd_outside_workspace_is_not_safe(self):
        p = self.policy()
        self.assertEqual(p.classify_command(["ls"], self.home, self.ws, False).level, Level.CONFIRM)


class UserPolicyTest(TempHome):
    def test_user_policy_only_tightens(self):  # PERM-006
        user = self.home / "user.toml"
        user.write_text("""
[limits]
max_tool_calls = 10
result_bytes = 99999999
[paths]
denied = ["~/secret-stuff"]
[commands]
blocked = ["npm"]
safe = [{ program = "ls" }, { program = "evil-new-program" }]
""")
        p = Policy.load(AI_ROOT / "policy" / "policy.toml", user=user)
        self.assertEqual(p.limit("max_tool_calls"), 10)
        self.assertEqual(p.limit("result_bytes"), 65536)  # cannot be raised
        self.assertEqual(p.classify_read(self.home / "secret-stuff/x", self.ws).level, Level.BLOCKED)
        self.assertEqual(p.classify_command(["npm", "test"], self.ws, self.ws, False).level, Level.BLOCKED)
        self.assertEqual(p.classify_command(["ls"], self.ws, self.ws, False).level, Level.SAFE)
        self.assertEqual(p.classify_command(["cat", "x"], self.ws, self.ws, False).level, Level.CONFIRM)
        self.assertEqual(p.classify_command(["evil-new-program"], self.ws, self.ws, False).level, Level.CONFIRM)
