import asyncio
import json

import pytest

from atgt.civil_rpc import CivilRpcClient, CivilRpcError


def test_rpc_correlates_response_and_surfaces_plugin_error():
    async def run():
        calls = 0
        async def handler(reader, writer):
            nonlocal calls
            request = json.loads((await reader.read(65536)).decode("utf-8"))
            calls += 1
            if calls == 1:
                response = {"jsonrpc": "2.0", "id": request["id"],
                            "result": {"connected": True, "drawingName": "sample.dwg"}}
            else:
                response = {"jsonrpc": "2.0", "id": request["id"],
                            "error": {"message": "active drawing changed"}}
            payload = json.dumps(response).encode("utf-8")
            if calls == 1:
                midpoint = len(payload) // 2
                writer.write(payload[:midpoint])
                await writer.drain()
                await asyncio.sleep(0.01)
                writer.write(payload[midpoint:])
            else:
                writer.write(payload)
            await writer.drain()
            writer.close()
        server = await asyncio.start_server(handler, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        async with server:
            client = CivilRpcClient("127.0.0.1", port, command_timeout_s=2)
            assert (await client.health())["drawingName"] == "sample.dwg"
            with pytest.raises(CivilRpcError, match="active drawing changed"):
                await client.query("return 1;")
    asyncio.run(run())
