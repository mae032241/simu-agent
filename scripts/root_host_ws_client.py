"""Bounded JSONL bridge to an app-server WebSocket over a private Unix socket.

Uses the optional host-probe dependency; never implements WebSocket framing itself.
"""
import argparse
import asyncio
import json
import sys

import aiohttp


async def bridge(path, limit):
    reader = asyncio.StreamReader(limit=limit)
    transport, _ = await asyncio.get_running_loop().connect_read_pipe(
        lambda: asyncio.StreamReaderProtocol(reader), sys.stdin.buffer)
    try:
        async with aiohttp.ClientSession(connector=aiohttp.UnixConnector(path=path),
                timeout=aiohttp.ClientTimeout(total=None, connect=10)) as session:
            async with session.ws_connect("http://localhost/", max_msg_size=limit) as ws:
                async def send():
                    while line := await reader.readline():
                        await ws.send_str(json.dumps(json.loads(line), ensure_ascii=False))

                async def receive():
                    async for message in ws:
                        if message.type == aiohttp.WSMsgType.TEXT:
                            print(json.dumps(json.loads(message.data), ensure_ascii=False), flush=True)
                        elif message.type == aiohttp.WSMsgType.ERROR:
                            raise RuntimeError("websocket_receive_failed") from ws.exception()
                        else:
                            raise RuntimeError("unexpected_websocket_message")

                tasks = [asyncio.create_task(send()), asyncio.create_task(receive())]
                try:
                    done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                    for task in done:
                        task.result()
                finally:
                    for task in tasks:
                        task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        transport.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--socket", required=True)
    parser.add_argument("--max-message-bytes", type=int, required=True)
    args = parser.parse_args()
    asyncio.run(bridge(args.socket, args.max_message_bytes))
