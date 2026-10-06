"""DevOS native agent runtime (SRS §14.2).

Runs inside a sandbox with no network and no access to the user's files. It
talks only to devosd over agent.sock: it asks devosd to call the model and to
run tools, one request at a time, until the model gives a final answer. All
policy, approval and execution happen in devosd.
"""

from __future__ import annotations

import asyncio
import os
import sys

from ..rpc import Client, RpcError


async def run() -> int:
    client = await Client().connect(os.environ["DEVOS_AGENT_SOCKET"])
    await client.call("task.attach", {"token": os.environ.pop("DEVOS_TASK_TOKEN")})
    task = await client.call("task.get")
    messages: list[dict] = list(task["messages"])
    final_text = ""
    while True:
        try:
            reply = await client.call("model.stream", {"messages": messages})
        except RpcError as e:
            await client.call("task.finish", {"text": str(e)})
            return 3
        message = reply["message"]
        messages.append(message)
        if message.get("text"):
            final_text = message["text"]
        calls = message.get("tool_calls") or []
        if not calls:
            break
        results = []
        for call in calls:
            result = await client.call("tools.call", {"name": call["name"], "args": call["args"], "id": call["id"]})
            results.append({"id": call["id"], "name": call["name"], "result": result})
        messages.append({"role": "tool", "results": results})
    await client.call("task.finish", {"text": final_text})
    await client.close()
    return 0


def main() -> None:
    sys.exit(asyncio.run(run()))


if __name__ == "__main__":
    main()
