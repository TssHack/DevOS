"""Remove secrets from anything that is logged or stored (SEC-004)."""

from __future__ import annotations

import re
import threading
from typing import Any

_PATTERNS = [
    re.compile(r"AIza[0-9A-Za-z_\-]{35}"),                       # Google API keys (Gemini)
    re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[0-9A-Za-z]{36,}\b"),  # GitHub tokens
    re.compile(r"\bgithub_pat_[0-9A-Za-z_]{40,}\b"),
    re.compile(r"\bglpat-[0-9A-Za-z_\-]{20,}\b"),                # GitLab
    re.compile(r"\bsk-(?:ant-|proj-)?[0-9A-Za-z_\-]{20,}\b"),     # "sk-" style provider keys
    re.compile(r"\bxox[abprs]-[0-9A-Za-z\-]{10,}\b"),             # Slack
    re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),                 # AWS access key id
    re.compile(r"\bnpm_[0-9A-Za-z]{36}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
]
_SECRET_ASSIGN = re.compile(
    r"(?i)\b([A-Z0-9_]*(?:PASSWORD|PASSWD|SECRET|TOKEN|API_?KEY|PRIVATE_?KEY)[A-Z0-9_]*)(\s*[=:]\s*)(\S+)")

_known: set[str] = set()
_lock = threading.Lock()
MASK = "[REDACTED]"


def register(secret: str | None) -> None:
    """Remember an exact secret (e.g. the user's API key) so it is always masked."""
    if secret and len(secret) >= 8:
        with _lock:
            _known.add(secret)


def text(s: str) -> str:
    with _lock:
        known = sorted(_known, key=len, reverse=True)
    for k in known:
        s = s.replace(k, MASK)
    for pat in _PATTERNS:
        s = pat.sub(MASK, s)
    return _SECRET_ASSIGN.sub(lambda m: m.group(1) + m.group(2) + MASK, s)


def value(v: Any) -> Any:
    """Redact strings inside nested JSON-like data."""
    if isinstance(v, str):
        return text(v)
    if isinstance(v, dict):
        return {k: value(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [value(x) for x in v]
    return v
