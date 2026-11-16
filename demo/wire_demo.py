#!/usr/bin/env python3
"""Show the raw MCP conversation between a host and the board server.

Run: python3 wire_demo.py
Launches pm_board_server.py as a subprocess, does the MCP handshake, lists the
tools, and calls a few of them, printing every JSON-RPC message on the wire.
This is exactly what an agent host does before the model ever sees a tool.
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GREEN, GOLD, DIM, RESET = "\033[32m", "\033[33m", "\033[2m", "\033[0m"

proc = subprocess.Popen([sys.executable, str(HERE / "pm_board_server.py")],
                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
next_id = 0


def send(method, params=None, notify=False, quiet=False):
    global next_id
    msg = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        msg["params"] = params
    if not notify:
        next_id += 1
        msg["id"] = next_id
    print(f"{GOLD}host -> server{RESET} {json.dumps(msg)}")
    proc.stdin.write(json.dumps(msg) + "\n")
    proc.stdin.flush()
    if notify:
        return None
    resp = json.loads(proc.stdout.readline())
    text = json.dumps(resp)
    print(f"{GREEN}server -> host{RESET} {DIM}{text[:400]}{'...' if len(text) > 400 else ''}{RESET}\n")
    return resp


send("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                    "clientInfo": {"name": "wire-demo", "version": "1"}})
send("notifications/initialized", notify=True)
tools = send("tools/list")["result"]["tools"]
print(f"{GOLD}Tools the model can now use:{RESET} {', '.join(t['name'] for t in tools)}\n")

risks = send("tools/call", {"name": "analyze_risks", "arguments": {}})
data = json.loads(risks["result"]["content"][0]["text"])
print(f"{GOLD}Top risks:{RESET}")
for r in data["risks"][:5]:
    print(f"  [{r['severity'].upper():6}] {r['detail']}{'  (critical path)' if r['critical_path'] else ''}")
print()

cp = json.loads(send("tools/call", {"name": "critical_path", "arguments": {}})["result"]["content"][0]["text"])
print(f"{GOLD}Critical path:{RESET} " + " -> ".join(p["id"] for p in cp["path"])
      + f"  ({cp['total_points']} pts, {cp['sprint_days_left']} days left)\n")

bad = send("tools/call", {"name": "update_task", "arguments": {"id": "R-999", "status": "done"}})
print(f"{GOLD}Errors come back to the model as data, so it can recover:{RESET} "
      f"{bad['result']['content'][0]['text']}")

proc.stdin.close()
proc.wait()
