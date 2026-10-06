"""Provider interface (SRS §13, PROV-001).

Messages use a provider-neutral format:
  {"role": "user",  "text": str}
  {"role": "model", "text": str, "tool_calls": [{"id", "name", "args"}], "raw": <provider data>}
  {"role": "tool",  "results": [{"id", "name", "result": dict}]}
Streams yield events:
  {"type": "text", "text": str}
  {"type": "tool_call", "id": str, "name": str, "args": dict}
  {"type": "done", "message": <model message>, "usage": dict, "finish_reason": str}
"""

from __future__ import annotations

from typing import AsyncIterator, Protocol


class ProviderError(Exception):
    """kind: invalid_key | quota | network | server | bad_request | cancelled"""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind

    def user_message(self) -> str:
        return {
            "invalid_key": "The API key was rejected. Check it in DevOS Settings.",
            "quota": "The provider's rate limit or quota was reached. Try again later.",
            "network": "Cannot reach the AI provider. Check your network connection.",
            "server": "The AI provider had an internal error. Try again.",
            "bad_request": "The AI provider rejected the request: " + str(self),
            "cancelled": "Cancelled.",
        }.get(self.kind, str(self))


class Provider(Protocol):
    name: str

    async def test_credentials(self) -> None: ...

    async def list_models(self) -> list[str]: ...

    def stream_chat(self, messages: list[dict], tools: list[dict] | None, system: str | None,
                    model: str) -> AsyncIterator[dict]: ...
