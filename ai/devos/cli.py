"""`devos` command line: a terminal client for devosd (and the headless UI).

  devos ai status | key set|test|remove|status | models
  devos ai chat [--conv ID] MESSAGE
  devos ai agent --workspace DIR [--conv ID] MESSAGE
  devos ai conversations | undo TASK [--force] | settings [KEY [VALUE]] | reset
  devos audit [-n N] [--json]
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import os
import sys

from . import PROTOCOL_VERSION, paths
from .audit import format_record
from .rpc import Client, RpcError

C = {"dim": "\033[2m", "bold": "\033[1m", "red": "\033[31m", "green": "\033[32m", "yellow": "\033[33m",
     "cyan": "\033[36m", "reset": "\033[0m"} if sys.stdout.isatty() else {k: "" for k in
                                                                            ("dim", "bold", "red", "green", "yellow", "cyan", "reset")}

STATE_ICON = {"running": "→", "done": "✓", "failed": "✗", "denied": "⊘", "blocked": "⊘"}


async def connect(on_notify=None) -> Client:
    try:
        client = await Client(on_notify).connect(paths.ui_socket())
    except (FileNotFoundError, ConnectionRefusedError):
        sys.exit(f"devosd is not running (expected {paths.ui_socket()}). "
                 "Start it with: systemctl --user start devosd.socket")
    await client.call("hello", {"protocol": PROTOCOL_VERSION})
    return client


def ask_tty(prompt: str) -> str:
    with open("/dev/tty") as tty:
        sys.stdout.write(prompt)
        sys.stdout.flush()
        return tty.readline().strip().lower()


def render_approval(a: dict) -> str:
    out = [f"\n{C['yellow']}{C['bold']}Approval needed{C['reset']}"]
    if a["kind"] == "continue":
        out.append(f"  {a['reason']}")
        return "\n".join(out)
    p = a.get("preview", {})
    out.append(f"  Tool:    {a['tool']}")
    if "argv" in p:
        out.append(f"  Run:     {C['bold']}{' '.join(p['argv'])}{C['reset']}")
        if "cwd" in p:
            out.append(f"  In:      {p['cwd']}")
        if "network" in p:
            out.append(f"  Network: {'ON' if p['network'] else 'off'}")
    elif "packages" in p:
        out.append(f"  {p['action'].capitalize()} packages: {' '.join(p['packages'])}")
    elif "path" in p:
        out.append(f"  File:    {p['path']}")
    out.append(f"  Why:     {a['reason']}")
    if p.get("diff"):
        for line in p["diff"].splitlines()[:80]:
            color = C["green"] if line.startswith("+") else C["red"] if line.startswith("-") else C["dim"]
            out.append(f"    {color}{line}{C['reset']}")
    if a.get("undoable") is False:
        out.append(f"  {C['red']}This change cannot be undone.{C['reset']}")
    return "\n".join(out)


async def cmd_agent(args) -> int:
    client: Client
    pending: asyncio.Queue = asyncio.Queue()

    def on_notify(method, p):
        if method == "agent.text":
            sys.stdout.write(p["text"])
            sys.stdout.flush()
        elif method == "agent.tool":
            icon = STATE_ICON.get(p["state"], "·")
            preview = p.get("preview", {})
            what = " ".join(preview["argv"]) if "argv" in preview else preview.get("path", "")
            color = C["red"] if p["state"] in ("failed", "denied", "blocked") else C["dim"]
            sys.stdout.write(f"\n{color}{icon} {p['tool']} {what}{C['reset']}")
            if p["state"] == "blocked":
                sys.stdout.write(f"{C['red']}  blocked: {p['reason']}{C['reset']}")
            sys.stdout.flush()
        elif method == "approval.request":
            pending.put_nowait(p)

    client = await connect(on_notify)
    await client.call("events.subscribe")
    if args.conv:
        conv = await client.call("conv.set_mode", {"id": args.conv, "mode": "agent", "workspace": args.workspace})
    else:
        conv = await client.call("conv.create", {"mode": "agent", "workspace": os.path.abspath(args.workspace)})

    async def approver():
        loop = asyncio.get_running_loop()
        while True:
            a = await pending.get()
            print(render_approval(a))
            opts = "[o]nce / [s]ession / [d]eny" if a.get("tool") == "execute_command" else \
                "[c]ontinue / [s]top" if a["kind"] == "continue" else "[a]pprove / [d]eny"
            ans = await loop.run_in_executor(None, ask_tty, f"  {opts}: ")
            decision = {"o": "once", "a": "once", "c": "once", "y": "once",
                        "s": "deny" if a["kind"] == "continue" else "session"}.get(ans[:1], "deny")
            if decision == "session" and a.get("tool") != "execute_command":
                decision = "deny"
            try:
                await client.call("approval.respond", {"id": a["id"], "decision": decision})
            except RpcError as e:
                print(f"  {e}")

    approver_task = asyncio.create_task(approver())
    try:
        summary = await client.call("agent.run", {"conv": conv["id"], "text": " ".join(args.message)})
    except KeyboardInterrupt:
        return 130
    finally:
        approver_task.cancel()
    print(f"\n\n{C['bold']}Task {summary['task']}: {summary['status']}{C['reset']}")
    if summary["files_changed"]:
        print("Files changed: " + ", ".join(summary["files_changed"]))
        print(f"Undo with: devos ai undo {summary['task']}")
    for c in summary["commands"]:
        print(f"  ran: {' '.join(c['argv'])} (exit {c['exit_code']})")
    if summary["sent_files"]:
        print(f"{C['dim']}Sent to Gemini: {', '.join(summary['sent_files'])}{C['reset']}")
    print(f"{C['dim']}Conversation: {conv['id']}{C['reset']}")
    await client.close()
    return 0 if summary["status"] == "completed" else 1


async def cmd_chat(args) -> int:
    def on_notify(method, p):
        if method == "chat.delta":
            sys.stdout.write(p["text"])
            sys.stdout.flush()

    client = await connect(on_notify)
    await client.call("events.subscribe")
    conv = await client.call("conv.get", {"id": args.conv}) if args.conv else \
        await client.call("conv.create", {"mode": "chat"})
    try:
        await client.call("chat.send", {"conv": conv["id"], "text": " ".join(args.message)})
    except RpcError as e:
        print(f"\n{C['red']}{e}{C['reset']}", file=sys.stderr)
        return 1
    print(f"\n{C['dim']}Conversation: {conv['id']}{C['reset']}")
    await client.close()
    return 0


async def cmd_key(args) -> int:
    client = await connect()
    if args.action == "set":
        key = getpass.getpass("Gemini API key: ") if sys.stdin.isatty() else sys.stdin.readline()
        r = await client.call("key.set", {"key": key})
        where = "the system keyring" if r["storage"] == "keyring" else \
            "memory only (no keyring available; it will be forgotten when devosd stops)"
        print(f"Saved to {where}.")
        args.action = "test"
    if args.action == "test":
        r = await client.call("key.test")
        print(f"{C['green']}Connection to Gemini works.{C['reset']}" if r["ok"] else f"{C['red']}{r['message']}{C['reset']}")
        return 0 if r["ok"] else 1
    if args.action == "remove":
        await client.call("key.remove")
        print("Key removed.")
    if args.action == "status":
        print((await client.call("key.status"))["status"])
    return 0


async def cmd_simple(args) -> int:
    client = await connect()
    a = args.ai_cmd
    if a == "status":
        h = await client.call("hello", {"protocol": PROTOCOL_VERSION})
        print(f"devosd {h['version']}  provider={h['provider']}  model={h['model']}  key={h['key']}")
        if h.get("settings_error"):
            print(f"{C['yellow']}{h['settings_error']}{C['reset']}")
    elif a == "models":
        r = await client.call("models.list")
        for m in r["models"]:
            print(("* " if m == r["current"] else "  ") + m)
    elif a == "conversations":
        for c in (await client.call("conv.list"))["conversations"]:
            ws = f"  {c['workspace']}" if c["workspace"] else ""
            print(f"{c['id']}  {c['mode']:5}  {c['title']}{ws}")
    elif a == "undo":
        r = await client.call("task.undo", {"task": args.task, "force": args.force})
        if r["status"] == "conflict":
            print("These files changed after the task finished; re-run with --force to overwrite them:")
            for f in r["files"]:
                print("  " + f)
            return 1
        print(f"Restored {len(r['restored'])} file(s), removed {len(r['removed'])} file(s).")
    elif a == "settings":
        if args.key and args.value is not None:
            section, key = args.key.split(".", 1)
            value = int(args.value) if args.value.isdigit() else args.value
            await client.call("settings.set", {"section": section, "key": key, "value": value})
        r = await client.call("settings.get")
        print(json.dumps(r, indent=2))
    elif a == "reset":
        if ask_tty("Delete all conversations, audit logs, checkpoints and the API key? [y/N] ") != "y":
            return 1
        await client.call("data.reset")
        print("All DevOS AI data removed.")
    await client.close()
    return 0


async def cmd_audit(args) -> int:
    from .audit import AuditLog
    records = AuditLog().tail(args.n)  # read directly: works without devosd
    for r in records:
        print(json.dumps(r) if args.json else format_record(r))
    return 0


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="devos", description="DevOS command line")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ai = sub.add_parser("ai", help="DevOS AI").add_subparsers(dest="ai_cmd", required=True)
    for name in ("status", "models", "conversations", "reset"):
        ai.add_parser(name)
    k = ai.add_parser("key")
    k.add_argument("action", choices=["set", "test", "remove", "status"])
    c = ai.add_parser("chat")
    c.add_argument("--conv")
    c.add_argument("message", nargs="+")
    g = ai.add_parser("agent")
    g.add_argument("--workspace", "-w", default=".")
    g.add_argument("--conv")
    g.add_argument("message", nargs="+")
    u = ai.add_parser("undo")
    u.add_argument("task")
    u.add_argument("--force", action="store_true")
    s = ai.add_parser("settings")
    s.add_argument("key", nargs="?")
    s.add_argument("value", nargs="?")
    au = sub.add_parser("audit", help="show the AI audit log")
    au.add_argument("-n", type=int, default=50)
    au.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if args.cmd == "audit":
        fn = cmd_audit
    else:
        fn = {"chat": cmd_chat, "agent": cmd_agent, "key": cmd_key}.get(args.ai_cmd, cmd_simple)
    try:
        sys.exit(asyncio.run(fn(args)))
    except RpcError as e:
        sys.exit(f"error: {e}")
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
