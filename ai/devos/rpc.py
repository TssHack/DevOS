"""JSON-RPC 2.0 over Unix stream sockets, one JSON object per line (ARCH-007).

Requests on one connection run concurrently, so a long call (a chat turn, an
agent task) can stream notifications while other calls are answered.
"""

from __future__ import annotations

import asyncio
import itertools
import json
import os
import socket
from pathlib import Path
from typing import Any, Awaitable, Callable

MAX_LINE = 16 * 1024 * 1024

# JSON-RPC error codes
PARSE_ERROR, INVALID_REQUEST, METHOD_NOT_FOUND, INVALID_PARAMS, INTERNAL = -32700, -32600, -32601, -32602, -32603
APP_ERROR = -32000


class RpcError(Exception):
    def __init__(self, message: str, code: int = APP_ERROR, data: Any = None):
        super().__init__(message)
        self.code, self.data = code, data

    def to_json(self) -> dict:
        e = {"code": self.code, "message": str(self)}
        if self.data is not None:
            e["data"] = self.data
        return e


class Connection:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader, self.writer = reader, writer
        self.closed = asyncio.Event()
        self.attrs: dict[str, Any] = {}
        self._lock = asyncio.Lock()

    async def send(self, msg: dict) -> None:
        if self.closed.is_set():
            return
        data = (json.dumps(msg, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
        async with self._lock:
            try:
                self.writer.write(data)
                await self.writer.drain()
            except (ConnectionError, RuntimeError):
                self.closed.set()

    async def notify(self, method: str, params: dict) -> None:
        await self.send({"jsonrpc": "2.0", "method": method, "params": params})

    def peer_uid(self) -> int | None:
        sock = self.writer.get_extra_info("socket")
        try:
            import struct
            creds = sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
            return struct.unpack("3i", creds)[1]
        except (OSError, AttributeError):
            return None


Handler = Callable[[Connection, str, dict], Awaitable[Any]]


class Server:
    def __init__(self, handler: Handler, on_connect=None, on_disconnect=None):
        self.handler = handler
        self.on_connect, self.on_disconnect = on_connect, on_disconnect
        self.connections: set[Connection] = set()
        self._server: asyncio.base_events.Server | None = None

    async def listen(self, path: Path | None = None, sock: socket.socket | None = None) -> None:
        if sock is None:
            assert path is not None
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            os.chmod(path.parent, 0o700)
            if path.exists() or path.is_symlink():
                path.unlink()
            old = os.umask(0o177)
            try:
                self._server = await asyncio.start_unix_server(self._serve, path=str(path), limit=MAX_LINE)
            finally:
                os.umask(old)
            os.chmod(path, 0o600)
        else:
            self._server = await asyncio.start_unix_server(self._serve, sock=sock, limit=MAX_LINE)

    async def _serve(self, reader, writer):
        conn = Connection(reader, writer)
        # Same user only (the sockets are 0600 anyway).
        uid = conn.peer_uid()
        if uid is not None and uid != os.getuid():
            writer.close()
            return
        self.connections.add(conn)
        if self.on_connect:
            self.on_connect(conn)
        pending: set[asyncio.Task] = set()
        try:
            while True:
                try:
                    line = await reader.readline()
                except (ConnectionError, ValueError):
                    break
                if not line:
                    break
                t = asyncio.create_task(self._dispatch(conn, line))
                pending.add(t)
                t.add_done_callback(pending.discard)
        finally:
            conn.closed.set()
            self.connections.discard(conn)
            for t in pending:
                t.cancel()
            if self.on_disconnect:
                self.on_disconnect(conn)
            writer.close()

    async def _dispatch(self, conn: Connection, line: bytes) -> None:
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            await conn.send({"jsonrpc": "2.0", "id": None, "error": {"code": PARSE_ERROR, "message": "parse error"}})
            return
        if not isinstance(msg, dict) or not isinstance(msg.get("method"), str):
            await conn.send({"jsonrpc": "2.0", "id": None,
                             "error": {"code": INVALID_REQUEST, "message": "invalid request"}})
            return
        mid, params = msg.get("id"), msg.get("params") or {}
        try:
            if not isinstance(params, dict):
                raise RpcError("params must be an object", INVALID_PARAMS)
            result = await self.handler(conn, msg["method"], params)
            if mid is not None:
                await conn.send({"jsonrpc": "2.0", "id": mid, "result": result})
        except RpcError as e:
            if mid is not None:
                await conn.send({"jsonrpc": "2.0", "id": mid, "error": e.to_json()})
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001 - never crash the daemon on a bad call
            if mid is not None:
                await conn.send({"jsonrpc": "2.0", "id": mid,
                                 "error": {"code": INTERNAL, "message": f"internal error: {e}"}})

    async def close(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        for c in list(self.connections):
            c.writer.close()


class Client:
    """Async JSON-RPC client. Notifications go to `on_notify(method, params)`."""

    def __init__(self, on_notify: Callable[[str, dict], Any] | None = None):
        self.on_notify = on_notify
        self._ids = itertools.count(1)
        self._pending: dict[int, asyncio.Future] = {}
        self._reader_task: asyncio.Task | None = None
        self._handlers: set[asyncio.Task] = set()

    async def connect(self, path: Path | str) -> "Client":
        self.reader, self.writer = await asyncio.open_unix_connection(str(path), limit=MAX_LINE)
        self._reader_task = asyncio.create_task(self._read_loop())
        return self

    async def _read_loop(self):
        try:
            while line := await self.reader.readline():
                msg = json.loads(line)
                if "id" in msg and msg["id"] in self._pending:
                    fut = self._pending.pop(msg["id"])
                    if not fut.done():
                        if "error" in msg:
                            e = msg["error"]
                            fut.set_exception(RpcError(e.get("message", "error"), e.get("code", APP_ERROR),
                                                       e.get("data")))
                        else:
                            fut.set_result(msg.get("result"))
                elif "method" in msg and self.on_notify:
                    r = self.on_notify(msg["method"], msg.get("params") or {})
                    if asyncio.iscoroutine(r):
                        # Run separately: a handler may itself call() and wait for a
                        # reply that only this loop can deliver.
                        t = asyncio.create_task(r)
                        self._handlers.add(t)
                        t.add_done_callback(self._handlers.discard)
        except (ConnectionError, asyncio.IncompleteReadError):
            pass
        finally:
            for fut in self._pending.values():
                if not fut.done():
                    fut.set_exception(ConnectionError("connection to devosd closed"))
            self._pending.clear()

    async def call(self, method: str, params: dict | None = None) -> Any:
        mid = next(self._ids)
        fut = asyncio.get_running_loop().create_future()
        self._pending[mid] = fut
        data = json.dumps({"jsonrpc": "2.0", "id": mid, "method": method, "params": params or {}}) + "\n"
        self.writer.write(data.encode())
        await self.writer.drain()
        return await fut

    async def close(self):
        if self._reader_task:
            self._reader_task.cancel()
        self.writer.close()
