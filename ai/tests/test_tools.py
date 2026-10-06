import asyncio
import subprocess

from util import TempHome, requires_sandbox

from devos import tools
from devos.checkpoints import CheckpointStore
from devos.policy import Level
from devos.tools import Context, ToolError


@requires_sandbox
class ToolsTest(TempHome):
    def ctx(self, checkpoint=None):
        return Context(policy=self.policy(), workspace=self.ws, checkpoint=checkpoint)

    def call(self, name, args, ctx=None):
        ctx = ctx or self.ctx()
        prepared = tools.get(name).prepare(args, ctx)
        return prepared, asyncio.run(prepared.execute(ctx))

    def test_read_list_search(self):
        (self.ws / "src").mkdir()
        (self.ws / "src/main.py").write_text("print('hello')\n# TODO fix\n")
        p, r = self.call("read_file", {"path": "src/main.py"})
        self.assertEqual(p.decision.level, Level.SAFE)
        self.assertIn("hello", r["content"])
        p, r = self.call("list_directory", {"depth": 2})
        self.assertIn("src/main.py", r["entries"])
        p, r = self.call("search_files", {"pattern": "TODO"})
        self.assertIn("main.py:2", r["matches"])

    def test_read_denied_and_sensitive(self):
        (self.home / ".ssh").mkdir()
        (self.home / ".ssh/id_rsa").write_text("k")
        (self.ws / ".env").write_text("X=1")
        ctx = self.ctx()
        self.assertEqual(tools.get("read_file").prepare({"path": "~/.ssh/id_rsa"}, ctx).decision.level, Level.BLOCKED)
        self.assertEqual(tools.get("read_file").prepare({"path": ".env"}, ctx).decision.level, Level.CONFIRM)

    def test_list_hides_denied_entries(self):
        (self.ws / ".git").mkdir()
        tools_ctx = self.ctx()
        tools_ctx.policy.denied.append(str(self.ws / "private"))
        (self.ws / "private").mkdir()
        p = tools.get("list_directory").prepare({}, tools_ctx)
        r = asyncio.run(p.execute(tools_ctx))
        self.assertNotIn("private/", r["entries"])

    def test_write_edit_with_diff_and_undo(self):
        f = self.ws / "app.py"
        f.write_text("x = 1\n")
        cp = CheckpointStore().open("task", self.ws)
        ctx = self.ctx(cp)
        p = tools.get("edit_file").prepare({"path": "app.py", "old": "x = 1", "new": "x = 2"}, ctx)
        self.assertEqual(p.decision.level, Level.CONFIRM)
        self.assertIn("-x = 1", p.preview["diff"])
        self.assertIn("+x = 2", p.preview["diff"])
        asyncio.run(p.execute(ctx))
        self.assertEqual(f.read_text(), "x = 2\n")
        cp.finish()
        cp.undo()
        self.assertEqual(f.read_text(), "x = 1\n")

    def test_edit_requires_unique_match(self):
        (self.ws / "a.txt").write_text("a a")
        with self.assertRaises(ToolError):
            tools.get("edit_file").prepare({"path": "a.txt", "old": "a", "new": "b"}, self.ctx())

    def test_write_outside_and_protected_blocked(self):
        ctx = self.ctx()
        self.assertEqual(tools.get("write_file").prepare({"path": "~/x.txt", "content": ""}, ctx).decision.level,
                         Level.BLOCKED)
        self.assertEqual(tools.get("write_file").prepare({"path": "~/.bashrc", "content": ""}, ctx).decision.level,
                         Level.BLOCKED)
        (self.ws / "d").mkdir()
        self.assertEqual(tools.get("delete_file").prepare({"path": "d"}, ctx).decision.level, Level.BLOCKED)

    def test_execute_command_sandboxed(self):
        p, r = self.call("execute_command", {"argv": ["sh", "-c", "echo hi > made.txt; echo done"]})
        self.assertEqual(p.decision.level, Level.CONFIRM)
        self.assertEqual(r["exit_code"], 0)
        self.assertTrue((self.ws / "made.txt").exists())

    def test_execute_command_undo(self):
        (self.ws / "keep.txt").write_text("v1")
        cp = CheckpointStore().open("task2", self.ws)
        ctx = self.ctx(cp)
        p = tools.get("execute_command").prepare(
            {"argv": ["sh", "-c", "echo v2 > keep.txt; echo new > new.txt"]}, ctx)
        asyncio.run(p.execute(ctx))
        cp.finish()
        cp.undo()
        self.assertEqual((self.ws / "keep.txt").read_text(), "v1")
        self.assertFalse((self.ws / "new.txt").exists())

    def test_git_tools(self):
        subprocess.run(["git", "init", "-q"], cwd=self.ws, check=True)
        subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=self.ws, check=True)
        subprocess.run(["git", "config", "user.name", "T"], cwd=self.ws, check=True)
        (self.ws / "a.txt").write_text("a")
        p, r = self.call("git_status", {})
        self.assertEqual(p.decision.level, Level.SAFE)
        self.assertIn("a.txt", r["stdout"])
        p, r = self.call("git_add", {"paths": ["a.txt"]})
        self.assertEqual(p.decision.level, Level.CONFIRM)
        p, r = self.call("git_commit", {"message": "first"})
        self.assertEqual(r["exit_code"], 0, r)
        p, r = self.call("git_log", {})
        self.assertIn("first", r["stdout"])
        with self.assertRaises(ToolError):
            tools.get("git_checkout").prepare({"name": "--orphan"}, self.ctx())
        self.assertEqual(tools.get("git_add").prepare({"paths": ["../x"]}, self.ctx()).decision.level, Level.BLOCKED)

    def test_system_tools(self):
        for name in ("system_info", "process_list", "disk_usage", "memory_usage"):
            p, r = self.call(name, {})
            self.assertEqual(p.decision.level, Level.SAFE)
            self.assertTrue(r)

    def test_kill_only_session_processes(self):
        self.assertEqual(tools.get("kill_process").prepare({"pid": 1}, self.ctx()).decision.level, Level.BLOCKED)

    def test_packages(self):
        p = tools.get("install_package").prepare({"names": ["htop"]}, self.ctx())
        self.assertEqual(p.decision.level, Level.CONFIRM)
        self.assertFalse(p.undoable)
        for bad in (["-Syu"], ["../x"], ["a b"], ["https://evil/pkg.tar.zst"]):
            with self.assertRaises(ToolError):
                tools.get("install_package").prepare({"names": bad}, self.ctx())

    def test_argument_validation(self):
        with self.assertRaises(ToolError):
            tools.get("read_file").prepare({}, self.ctx())
        with self.assertRaises(ToolError):
            tools.get("read_file").prepare({"path": 1}, self.ctx())
        with self.assertRaises(ToolError):
            tools.get("read_file").prepare({"path": "a", "evil": True}, self.ctx())
        with self.assertRaises(ToolError):
            tools.get("execute_command").prepare({"argv": "ls"}, self.ctx())
