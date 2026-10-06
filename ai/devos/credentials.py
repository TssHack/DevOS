"""API key storage in the Secret Service (SRS AI-004, D-11).

The key is stored only in the desktop keyring via libsecret's `secret-tool`.
If no Secret Service is available it is kept in memory for this session only.
It is never written to disk by DevOS, never put in a child's environment, and
registered with the redactor so it cannot reach logs.
"""

from __future__ import annotations

import shutil
import subprocess

from . import redact

ATTRS = ["service", "devos", "provider"]


class SecretToolBackend:
    def __init__(self, timeout: float = 15):
        self.timeout = timeout

    def available(self) -> bool:
        return shutil.which("secret-tool") is not None

    def _run(self, args: list[str], stdin: str | None = None) -> subprocess.CompletedProcess:
        # Minimal environment for the helper: it needs only the session bus.
        import os
        env = {k: v for k, v in os.environ.items()
               if k in ("DBUS_SESSION_BUS_ADDRESS", "XDG_RUNTIME_DIR", "HOME", "PATH", "LANG")}
        return subprocess.run(["secret-tool", *args], input=stdin, capture_output=True, text=True,
                              timeout=self.timeout, env=env)

    def store(self, provider: str, secret: str) -> bool:
        r = self._run(["store", "--label", f"DevOS {provider} API key", *ATTRS, provider], stdin=secret)
        return r.returncode == 0

    def lookup(self, provider: str) -> str | None:
        r = self._run(["lookup", *ATTRS, provider])
        return r.stdout if r.returncode == 0 and r.stdout else None

    def clear(self, provider: str) -> None:
        self._run(["clear", *ATTRS, provider])


class Credentials:
    def __init__(self, backend=None):
        self.backend = backend if backend is not None else SecretToolBackend()
        self._memory: dict[str, str] = {}
        self._cache: dict[str, str] = {}

    def set(self, provider: str, secret: str) -> str:
        """Store a key. Returns 'keyring' or 'memory' (session only)."""
        secret = secret.strip()
        if not secret or any(c.isspace() for c in secret):
            raise ValueError("the API key must be a single non-empty token")
        redact.register(secret)
        self._cache[provider] = secret
        try:
            if self.backend.available() and self.backend.store(provider, secret):
                self._memory.pop(provider, None)
                return "keyring"
        except (OSError, subprocess.SubprocessError):
            pass
        self._memory[provider] = secret
        return "memory"

    def get(self, provider: str) -> str | None:
        if provider in self._cache:
            return self._cache[provider]
        secret = self._memory.get(provider)
        if secret is None:
            try:
                if self.backend.available():
                    secret = self.backend.lookup(provider)
            except (OSError, subprocess.SubprocessError):
                secret = None
        if secret:
            redact.register(secret)
            self._cache[provider] = secret
        return secret

    def remove(self, provider: str) -> None:
        self._cache.pop(provider, None)
        self._memory.pop(provider, None)
        try:
            if self.backend.available():
                self.backend.clear(provider)
        except (OSError, subprocess.SubprocessError):
            pass

    def status(self, provider: str) -> str:
        """'keyring' | 'memory' | 'missing'"""
        if provider in self._memory:
            return "memory"
        return "keyring" if self.get(provider) else "missing"
