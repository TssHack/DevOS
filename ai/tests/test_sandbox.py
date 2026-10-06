"""Sandbox escape tests (SRS A-18, SBX-001..006). These run real bubblewrap."""

import asyncio
import os
import unittest
from pathlib import Path

from util import TempHome, requires_sandbox

from devos import sandbox


@requires_sandbox
class SandboxTest(TempHome):
    def run_cmd(self, argv, **kw):
        spec = sandbox.Spec(argv=argv, cwd=kw.pop("cwd", self.ws), workspace=self.ws, **kw)
        return asyncio.run(sandbox.run(spec, self.policy(), output_limit=kw.pop("limit", None)))

    def sh(self, script, **kw):
        return self.run_cmd(["sh", "-c", script], **kw)

    def test_workspace_is_writable(self):
        r = self.sh("echo hi > out.txt && cat out.txt")
        self.assertEqual((r.exit_code, r.stdout), (0, "hi\n"))
        self.assertEqual((self.ws / "out.txt").read_text(), "hi\n")

    def test_outside_workspace_is_read_only(self):
        (self.home / "notes.txt").write_text("keep")
        r = self.sh(f"echo pwned > {self.home}/notes.txt")
        self.assertNotEqual(r.exit_code, 0)
        self.assertEqual((self.home / "notes.txt").read_text(), "keep")
        r = self.sh(f"touch {self.home}/new-file")
        self.assertNotEqual(r.exit_code, 0)
        self.assertFalse((self.home / "new-file").exists())

    def test_denied_paths_are_masked(self):
        (self.home / ".ssh").mkdir()
        (self.home / ".ssh/id_ed25519").write_text("PRIVATE")
        (self.home / ".netrc").write_text("machine x password y")
        r = self.sh(f"cat {self.home}/.ssh/id_ed25519; ls -A {self.home}/.ssh; cat {self.home}/.netrc")
        self.assertNotIn("PRIVATE", r.stdout)
        self.assertNotIn("password", r.stdout)

    def test_runtime_dir_hidden(self):  # no D-Bus / Secret Service / ssh-agent
        rt = Path(os.environ["XDG_RUNTIME_DIR"])
        (rt / "bus").write_text("socket stand-in")
        r = self.sh(f"ls -A {rt}; ls -A /run")
        self.assertNotIn("bus", r.stdout)

    def test_environment_is_scrubbed(self):
        os.environ["GITHUB_TOKEN"] = "ghp_secret"
        os.environ["SSH_AUTH_SOCK"] = "/tmp/agent.sock"
        r = self.run_cmd(["env"])
        self.assertNotIn("ghp_secret", r.stdout)
        self.assertNotIn("SSH_AUTH_SOCK", r.stdout)
        self.assertIn("CI=1", r.stdout)

    def test_no_network_by_default(self):
        code = "import socket\ntry:\n socket.create_connection(('1.1.1.1', 53), timeout=3); print('CONNECTED')\nexcept OSError as e: print('BLOCKED', e)"
        r = self.run_cmd(["python3", "-c", code])
        self.assertIn("BLOCKED", r.stdout)

    def test_no_new_privileges(self):
        r = self.sh("grep NoNewPrivs /proc/self/status")
        self.assertIn("1", r.stdout)

    def test_pid_namespace(self):
        r = self.sh("ls /proc | grep -c '^[0-9]'")
        self.assertLess(int(r.stdout.strip()), 10)

    def test_timeout_kills(self):
        r = self.run_cmd(["sleep", "30"], timeout=1)
        self.assertTrue(r.timed_out)
        self.assertIsNone(r.exit_code)
        self.assertLess(r.duration_ms, 10000)

    def test_output_is_truncated(self):
        spec = sandbox.Spec(argv=["sh", "-c", "head -c 200000 /dev/zero | tr '\\0' a"], cwd=self.ws, workspace=self.ws)
        r = asyncio.run(sandbox.run(spec, self.policy(), output_limit=1000))
        self.assertEqual(len(r.stdout), 1000)
        self.assertTrue(r.truncated)

    def test_hide_home(self):
        (self.home / "secret.txt").write_text("s")
        spec = sandbox.Spec(argv=["sh", "-c", f"ls -A {self.home}"], cwd=Path("/"), workspace=None, hide_home=True)
        r = asyncio.run(sandbox.run(spec, self.policy()))
        self.assertEqual(r.stdout.strip(), "")
