"""Bounded JSON-RPC client for the local Civil 3D Roslyn listener."""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any


class CivilRpcError(RuntimeError):
    """The local Civil listener was unreachable or rejected a command."""


class CivilRpcClient:
    def __init__(self, host: str, port: int, connect_timeout_s: float = 5,
                 command_timeout_s: float = 30, max_response_bytes: int = 16 * 1024 * 1024):
        if host not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("Civil RPC must use a loopback host")
        if not 1 <= port <= 65535:
            raise ValueError("Civil RPC port must be 1..65535")
        if not 0.1 <= connect_timeout_s <= 30 or not 1 <= command_timeout_s <= 120:
            raise ValueError("Civil RPC timeouts are outside the safe local bounds")
        self.host = host
        self.port = port
        self.connect_timeout_s = connect_timeout_s
        self.command_timeout_s = command_timeout_s
        self.max_response_bytes = max_response_bytes

    async def call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        request = {"jsonrpc": "2.0", "method": method, "params": params or {},
                   "id": str(time.time_ns())}
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), self.connect_timeout_s)
        except (OSError, asyncio.TimeoutError) as exc:
            raise CivilRpcError(
                f"Civil listener is not reachable at {self.host}:{self.port}; "
                "verify the intended drawing and run C3DMCPSTART") from exc
        try:
            writer.write(json.dumps(request, ensure_ascii=False).encode("utf-8"))
            await writer.drain()
            async def read_response() -> Any:
                data = bytearray()
                last_error: Exception | None = None
                while len(data) <= self.max_response_bytes:
                    chunk = await reader.read(min(64 * 1024,
                                                  self.max_response_bytes + 1 - len(data)))
                    if not chunk:
                        break
                    data.extend(chunk)
                    if len(data) > self.max_response_bytes:
                        raise CivilRpcError("Civil listener response exceeded the configured limit")
                    try:
                        return json.loads(data.decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                        last_error = exc
                if not data:
                    raise CivilRpcError("Civil listener returned an empty response")
                raise CivilRpcError("Civil listener returned an invalid JSON response") from last_error

            response = await asyncio.wait_for(read_response(), self.command_timeout_s)
            if response.get("error"):
                error = response["error"]
                message = error.get("message") if isinstance(error, dict) else str(error)
                raise CivilRpcError(message or "Civil listener rejected the command")
            if response.get("id") not in {None, request["id"]}:
                raise CivilRpcError("Civil listener returned a mismatched response id")
            return response.get("result")
        except asyncio.TimeoutError as exc:
            raise CivilRpcError(
                "Civil command timed out; inspect the drawing before deciding whether to continue. "
                "Do not repeat a write command automatically") from exc
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass

    async def health(self) -> dict[str, Any]:
        result = await self.call("getCivil3DHealth")
        if not isinstance(result, dict):
            raise CivilRpcError("Civil health response has an unexpected shape")
        return result

    async def query(self, code: str) -> Any:
        return await self.call("executeCode", {"code": code, "readOnly": True})

    async def execute(self, code: str, description: str) -> Any:
        return await self.call("executeCode", {
            "code": code, "readOnly": False, "description": description})
