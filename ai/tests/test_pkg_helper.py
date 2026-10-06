"""devos-pkg-helper validation (SRS PRIV-001..003, A-20), with root and pacman mocked."""

import importlib.machinery
import importlib.util
import os
import unittest
from unittest import mock

from util import AI_ROOT

PATH = AI_ROOT / "system/bin/devos-pkg-helper"


def load():
    loader = importlib.machinery.SourceFileLoader("devos_pkg_helper", str(PATH))
    spec = importlib.util.spec_from_loader("devos_pkg_helper", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


class PkgHelperTest(unittest.TestCase):
    def run_helper(self, *args, root=True, pkexec=True):
        mod = load()
        env = {"PKEXEC_UID": "1000"} if pkexec else {}
        with mock.patch.object(mod.os, "geteuid", return_value=0 if root else 1000), \
                mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(mod.subprocess, "run") as run:
            run.return_value.returncode = 0
            with self.assertRaises(SystemExit) as cm:
                mod.main(list(args))
            return cm.exception.code, (run.call_args[0][0] if run.called else None)

    def test_install(self):
        code, cmd = self.run_helper("install", "htop", "ripgrep")
        self.assertEqual(code, 0)
        self.assertEqual(cmd, ["pacman", "-S", "--needed", "--noconfirm", "--noprogressbar", "--", "htop", "ripgrep"])

    def test_remove(self):
        code, cmd = self.run_helper("remove", "htop")
        self.assertEqual(cmd[:2], ["pacman", "-R"])

    def test_rejects(self):
        for args in (("install", "-Syu"), ("install", "--overwrite=*"), ("install", "../x"),
                     ("install", "https://evil/x.pkg.tar.zst"), ("install", "local.pkg.tar.zst"),
                     ("install", "Upper"), ("upgrade", "x"), ("install",),
                     ("remove", "linux"), ("remove", "systemd"), ("remove", "devos-ai"), ("remove", "sudo")):
            code, cmd = self.run_helper(*args)
            self.assertEqual(code, 2, args)
            self.assertIsNone(cmd, args)

    def test_requires_pkexec_root(self):
        self.assertEqual(self.run_helper("install", "htop", root=False), (2, None))
        self.assertEqual(self.run_helper("install", "htop", pkexec=False), (2, None))
