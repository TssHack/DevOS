"""Google Gemini provider over the documented REST API (PROV-004). HTTPS only;
the key travels in the x-goog-api-key header, never in URLs."""

from __future__ import annotations

import asyncio
import json
import threading
import urllib.error
import urllib.request
from typing import AsyncIterator, Callable

from .base import ProviderError

DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
RETRYABLE = {"quota", "server", "network"}


class Gemini:
    name = "gemini"

    def __init__(self, get_key: Callable[[], str | None], base_url: str = DEFAULT_BASE_URL,
                 timeout: float = 120, max_retries: int = 2, backoff: float = 1.0):
        if not (base_url.startswith("https://") or base_url.startswith("http://127.0.0.1")):
            raise ValueError("Gemini base URL must use HTTPS")
        self._get_key = get_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff = backoff

    # ------------------------------------------------------------- HTTP basics
    def _request(self, method: str, path: str, body: dict | None = None):
        key = self._get_key()
        if not key:
            raise ProviderError("invalid_key", "no API key configured")
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base_url + path, data=data, method=method, headers={
            "x-goog-api-key": key, "Content-Type": "application/json", "User-Agent": "devosd/0.1"})
        try:
            return urllib.request.urlopen(req, timeout=self.timeout)
        except urllib.error.HTTPError as e:
            raise _http_error(e) from None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise ProviderError("network", str(getattr(e, "reason", e))) from None

    async def test_credentials(self) -> None:
        """AI-005: one minimal authenticated request."""
        def call():
            with self._request("GET", "/models?pageSize=1") as r:
                r.read()
        await asyncio.to_thread(call)

    async def list_models(self) -> list[str]:
        def call():
            with self._request("GET", "/models?pageSize=200") as r:
                return json.loads(r.read())
        data = await asyncio.to_thread(call)
        return sorted(m["name"].removeprefix("models/") for m in data.get("models", [])
                      if "generateContent" in m.get("supportedGenerationMethods", []))

    # --------------------------------------------------------------- streaming
    async def stream_chat(self, messages: list[dict], tools: list[dict] | None, system: str | None,
                          model: str) -> AsyncIterator[dict]:
        body: dict = {"contents": to_contents(messages)}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        if tools:
            body["tools"] = [{"functionDeclarations": [to_declaration(t) for t in tools]}]
        path = f"/models/{model}:streamGenerateContent?alt=sse"

        attempt = 0
        while True:
            produced = False
            try:
                async for ev in self._stream_once(path, body):
                    produced = True
                    yield ev
                return
            except ProviderError as e:
                # AI-012: retry only transient failures, and only before any output.
                if e.kind not in RETRYABLE or produced or attempt >= self.max_retries:
                    raise
                await asyncio.sleep(self.backoff * (2 ** attempt))
                attempt += 1

    async def _stream_once(self, path: str, body: dict) -> AsyncIterator[dict]:
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()
        stop = threading.Event()
        holder: dict = {}

        def worker():
            try:
                resp = self._request("POST", path, body)
                holder["resp"] = resp
                with resp:
                    for raw in resp:
                        if stop.is_set():
                            return
                        line = raw.decode().strip()
                        if line.startswith("data:"):
                            loop.call_soon_threadsafe(queue.put_nowait, ("chunk", json.loads(line[5:])))
                loop.call_soon_threadsafe(queue.put_nowait, ("end", None))
            except ProviderError as e:
                loop.call_soon_threadsafe(queue.put_nowait, ("error", e))
            except Exception as e:  # noqa: BLE001 - surface any transport failure
                if not stop.is_set():
                    loop.call_soon_threadsafe(queue.put_nowait, ("error", ProviderError("network", str(e))))

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        parts: list[dict] = []
        text, calls, usage, finish = [], [], {}, ""
        try:
            while True:
                kind, payload = await queue.get()
                if kind == "error":
                    raise payload
                if kind == "end":
                    break
                if "error" in payload:
                    raise ProviderError("server", payload["error"].get("message", "error"))
                usage = payload.get("usageMetadata", usage)
                for cand in payload.get("candidates", [])[:1]:
                    finish = cand.get("finishReason", finish)
                    for part in cand.get("content", {}).get("parts", []):
                        parts.append(part)
                        if "text" in part and not part.get("thought"):
                            text.append(part["text"])
                            yield {"type": "text", "text": part["text"]}
                        elif "functionCall" in part:
                            fc = part["functionCall"]
                            call = {"id": fc.get("id") or f"call_{len(calls)}", "name": fc["name"],
                                    "args": fc.get("args", {})}
                            calls.append(call)
                            yield {"type": "tool_call", **call}
                if finish in ("SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII"):
                    raise ProviderError("bad_request", f"response blocked by the provider ({finish})")
        except asyncio.CancelledError:
            stop.set()
            resp = holder.get("resp")
            if resp is not None:
                try:
                    resp.close()
                except Exception:  # noqa: BLE001
                    pass
            raise
        message = {"role": "model", "text": "".join(text), "tool_calls": calls, "raw": parts}
        yield {"type": "done", "message": message, "finish_reason": finish,
               "usage": {"input_tokens": usage.get("promptTokenCount"),
                         "output_tokens": usage.get("candidatesTokenCount")}}


# ------------------------------------------------------------------ conversion

def to_contents(messages: list[dict]) -> list[dict]:
    out = []
    for m in messages:
        if m["role"] == "user":
            out.append({"role": "user", "parts": [{"text": m["text"]}]})
        elif m["role"] == "model":
            # Keep provider parts verbatim: they carry thought signatures that
            # Gemini requires back in follow-up turns.
            parts = m.get("raw") or ([{"text": m["text"]}] if m.get("text") else []) + [
                {"functionCall": {"name": c["name"], "args": c["args"]}} for c in m.get("tool_calls", [])]
            if parts:
                out.append({"role": "model", "parts": parts})
        elif m["role"] == "tool":
            out.append({"role": "user", "parts": [
                {"functionResponse": {"name": r["name"], "response": r["result"]}} for r in m["results"]]})
    return out


_SCHEMA_KEYS = {"type", "description", "properties", "required", "items", "enum", "minimum", "maximum"}


def _schema(s: dict) -> dict:
    out = {k: v for k, v in s.items() if k in _SCHEMA_KEYS}
    if "properties" in out:
        out["properties"] = {k: _schema(v) for k, v in out["properties"].items()}
    if "items" in out:
        out["items"] = _schema(out["items"])
    return out


def to_declaration(tool: dict) -> dict:
    d = {"name": tool["name"], "description": tool["description"]}
    schema = tool.get("inputSchema") or {}
    if schema.get("properties"):  # Gemini rejects OBJECT schemas without properties
        d["parameters"] = _schema(schema)
    return d


def _http_error(e: urllib.error.HTTPError) -> ProviderError:
    try:
        detail = json.loads(e.read()).get("error", {})
        msg, status = detail.get("message", str(e)), detail.get("status", "")
    except Exception:  # noqa: BLE001
        msg, status = str(e), ""
    finally:
        e.close()
    if e.code in (401, 403) or "API_KEY_INVALID" in msg or "API key not valid" in msg:
        return ProviderError("invalid_key", msg)
    if e.code == 429 or status == "RESOURCE_EXHAUSTED":
        return ProviderError("quota", msg)
    if e.code >= 500:
        return ProviderError("server", msg)
    return ProviderError("bad_request", msg)
