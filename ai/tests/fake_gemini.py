"""A local stand-in for the Gemini REST API, scripted per test."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VALID_KEY = "AIza" + "T" * 35


class FakeGemini:
    """`script` is a list of responses consumed per streamGenerateContent call:
    either a list of SSE chunk dicts, or an int HTTP status for an error."""

    def __init__(self):
        self.script: list = []
        self.requests: list[dict] = []
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _deny(self):
                if self.headers.get("x-goog-api-key") != VALID_KEY:
                    self._error(400, "API key not valid. Please pass a valid API key.", "INVALID_ARGUMENT")
                    return True
                return False

            def _error(self, code, msg, status):
                body = json.dumps({"error": {"code": code, "message": msg, "status": status}}).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self._deny():
                    return
                body = json.dumps({"models": [
                    {"name": "models/gemini-flash-latest", "supportedGenerationMethods": ["generateContent"]},
                    {"name": "models/embedding-001", "supportedGenerationMethods": ["embedContent"]}]}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                fake.requests.append({"path": self.path, "body": body})
                if self._deny():
                    return
                step = fake.script.pop(0) if fake.script else [{"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}]
                if isinstance(step, int):
                    self._error(step, "scripted error", "RESOURCE_EXHAUSTED" if step == 429 else "INTERNAL")
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                for chunk in step:
                    self.wfile.write(b"data: " + json.dumps(chunk).encode() + b"\r\n\r\n")
                    self.wfile.flush()

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}/v1beta"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def text_chunk(t):
    return {"candidates": [{"content": {"role": "model", "parts": [{"text": t}]}}]}


def call_chunk(name, args, signature="sig-1"):
    return {"candidates": [{"content": {"role": "model", "parts": [
        {"functionCall": {"name": name, "args": args}, "thoughtSignature": signature}]}}]}


def done_chunk():
    return {"candidates": [{"content": {"parts": []}, "finishReason": "STOP"}],
            "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5}}
