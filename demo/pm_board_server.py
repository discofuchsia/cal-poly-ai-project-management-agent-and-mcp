#!/usr/bin/env python3
"""Mustang Rover project board: a tiny MCP server for the talk demo.

Speaks the Model Context Protocol (JSON-RPC 2.0) over stdio, using only the
Python standard library, so any MCP host (Kiro, Claude Desktop, VS Code, etc.)
can launch it with `python3 pm_board_server.py`. It opens no network port.

State lives in board.json next to this file. Run with --reset to rebuild it
from seed_board.json with due dates relative to today.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEED = HERE / "seed_board.json"
BOARD = HERE / "board.json"
PROTOCOL_VERSION = "2024-11-05"
STATUSES = ["todo", "in_progress", "blocked", "done"]


# ---------------------------------------------------------------- board state
def reset_board() -> dict:
    seed = json.loads(SEED.read_text())
    today = dt.date.today()
    for t in seed["tasks"]:
        t["due"] = (today + dt.timedelta(days=t.pop("due_in_days"))).isoformat()
        t.setdefault("notes", [])
    seed["sprint_end"] = (today + dt.timedelta(days=seed.pop("sprint_ends_in_days"))).isoformat()
    seed["activity"] = []
    save(seed)
    return seed


def load() -> dict:
    if not BOARD.exists():
        return reset_board()
    return json.loads(BOARD.read_text())


def save(board: dict) -> None:
    BOARD.write_text(json.dumps(board, indent=2))


def by_id(board: dict) -> dict:
    return {t["id"]: t for t in board["tasks"]}


def days_until(iso: str) -> int:
    return (dt.date.fromisoformat(iso) - dt.date.today()).days


def open_tasks(board: dict) -> list:
    return [t for t in board["tasks"] if t["status"] != "done"]


# ---------------------------------------------------------------- analysis
def compute_critical_path(board: dict) -> dict:
    """Longest chain of unfinished work (by story points) through dependencies."""
    tasks = by_id(board)
    memo: dict = {}

    def longest(tid: str) -> tuple:
        if tid in memo:
            return memo[tid]
        t = tasks[tid]
        best = (0, [])
        for dep in t["depends_on"]:
            if dep in tasks and tasks[dep]["status"] != "done":
                cand = longest(dep)
                if cand[0] > best[0]:
                    best = cand
        memo[tid] = (best[0] + t["points"], best[1] + [tid])
        return memo[tid]

    chains = [longest(t["id"]) for t in open_tasks(board)]
    points, path = max(chains, default=(0, []))
    days_left = days_until(board["sprint_end"])
    return {
        "path": [{"id": i, "title": tasks[i]["title"], "assignee": tasks[i]["assignee"],
                  "status": tasks[i]["status"], "points": tasks[i]["points"]} for i in path],
        "total_points": points,
        "sprint_days_left": days_left,
    }


def compute_workload(board: dict) -> list:
    cap = board["capacity_points_per_person"]
    rows = []
    for m in board["team"]:
        mine = [t for t in open_tasks(board) if t["assignee"] == m["name"]]
        pts = sum(t["points"] for t in mine)
        rows.append({"name": m["name"], "role": m["role"], "open_points": pts,
                     "capacity": cap, "load_pct": round(100 * pts / cap),
                     "overloaded": pts > cap, "tasks": [t["id"] for t in mine]})
    return sorted(rows, key=lambda r: -r["open_points"])


def compute_risks(board: dict) -> list:
    tasks = by_id(board)
    crit = {p["id"] for p in compute_critical_path(board)["path"]}
    risks = []
    for t in open_tasks(board):
        d = days_until(t["due"])
        on_cp = t["id"] in crit
        if t["status"] == "blocked":
            risks.append({"severity": "high", "type": "blocked", "task": t["id"],
                          "detail": f'{t["title"]} is blocked: {t.get("blocked_reason", "no reason given")}',
                          "critical_path": on_cp})
        if d < 0:
            risks.append({"severity": "high" if on_cp or t["priority"] in ("high", "critical") else "medium",
                          "type": "overdue", "task": t["id"],
                          "detail": f'{t["title"]} is {-d} day(s) overdue ({t["assignee"] or "unassigned"})',
                          "critical_path": on_cp})
        if not t["assignee"]:
            risks.append({"severity": "high" if t["priority"] == "critical" else "medium",
                          "type": "unassigned", "task": t["id"],
                          "detail": f'{t["title"]} ({t["priority"]}) has no owner and is due in {d} day(s)',
                          "critical_path": on_cp})
        waiting = [x for x in t["depends_on"] if x in tasks and tasks[x]["status"] == "blocked"]
        if waiting:
            risks.append({"severity": "high", "type": "dependency", "task": t["id"],
                          "detail": f'{t["title"]} depends on blocked work: {", ".join(waiting)}',
                          "critical_path": on_cp})
    for w in compute_workload(board):
        if w["overloaded"]:
            risks.append({"severity": "medium", "type": "overload", "task": None,
                          "detail": f'{w["name"]} has {w["open_points"]} open points against a capacity of {w["capacity"]} ({w["load_pct"]}%)',
                          "critical_path": any(i in crit for i in w["tasks"])})
    order = {"high": 0, "medium": 1, "low": 2}
    return sorted(risks, key=lambda r: (order[r["severity"]], not r["critical_path"]))


# ---------------------------------------------------------------- tools
def tool_list_tasks(args: dict) -> dict:
    board = load()
    rows = board["tasks"]
    if args.get("status"):
        rows = [t for t in rows if t["status"] == args["status"]]
    if args.get("assignee"):
        rows = [t for t in rows if (t["assignee"] or "").lower().startswith(args["assignee"].lower())]
    return {"project": board["project"], "sprint": board["sprint"],
            "sprint_end": board["sprint_end"], "count": len(rows),
            "tasks": [{k: t[k] for k in ("id", "title", "assignee", "status", "points", "due", "priority", "depends_on")} for t in rows]}


def tool_get_task(args: dict) -> dict:
    t = by_id(load()).get(args["id"])
    if not t:
        raise ValueError(f'No task {args["id"]}')
    return t


def tool_update_task(args: dict) -> dict:
    board = load()
    t = by_id(board).get(args["id"])
    if not t:
        raise ValueError(f'No task {args["id"]}')
    changes = []
    if "status" in args:
        if args["status"] not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}")
        changes.append(f'status {t["status"]} -> {args["status"]}')
        t["status"] = args["status"]
    if "assignee" in args:
        names = {m["name"] for m in board["team"]}
        if args["assignee"] not in names:
            raise ValueError(f"assignee must be one of {sorted(names)}")
        changes.append(f'assignee {t["assignee"] or "unassigned"} -> {args["assignee"]}')
        t["assignee"] = args["assignee"]
    if args.get("note"):
        t["notes"].append(args["note"])
        changes.append("note added")
    if not changes:
        raise ValueError("Nothing to update: pass status, assignee or note")
    board["activity"].append({"at": dt.datetime.now().isoformat(timespec="seconds"),
                              "task": t["id"], "changes": changes, "by": "pm-agent"})
    save(board)
    return {"updated": t["id"], "changes": changes}


def tool_analyze_risks(args: dict) -> dict:
    board = load()
    return {"as_of": dt.date.today().isoformat(), "risks": compute_risks(board)}


def tool_critical_path(args: dict) -> dict:
    return compute_critical_path(load())


def tool_team_workload(args: dict) -> dict:
    return {"workload": compute_workload(load())}


def tool_sprint_summary(args: dict) -> dict:
    board = load()
    tasks = board["tasks"]
    total = sum(t["points"] for t in tasks)
    done = sum(t["points"] for t in tasks if t["status"] == "done")
    by_status = {s: [t["id"] for t in tasks if t["status"] == s] for s in STATUSES}
    return {"project": board["project"], "sprint": board["sprint"],
            "sprint_end": board["sprint_end"], "days_left": days_until(board["sprint_end"]),
            "points_total": total, "points_done": done,
            "pct_complete": round(100 * done / total), "by_status": by_status,
            "risks": compute_risks(board), "critical_path": compute_critical_path(board),
            "recent_activity": board["activity"][-10:]}


TOOLS = {
    "list_tasks": (tool_list_tasks, "List tasks on the sprint board. Optional filters: status, assignee.",
                   {"type": "object", "properties": {
                       "status": {"type": "string", "enum": STATUSES},
                       "assignee": {"type": "string", "description": "Name or first name"}}}),
    "get_task": (tool_get_task, "Get one task with notes and blocked reason.",
                 {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]}),
    "update_task": (tool_update_task, "Change a task's status or assignee, or add a note. Writes to the board; ask the human first.",
                    {"type": "object", "properties": {
                        "id": {"type": "string"},
                        "status": {"type": "string", "enum": STATUSES},
                        "assignee": {"type": "string"},
                        "note": {"type": "string"}}, "required": ["id"]}),
    "analyze_risks": (tool_analyze_risks, "Deterministic risk scan: blocked, overdue, unassigned, blocked dependencies and overloaded people, sorted by severity.",
                      {"type": "object", "properties": {}}),
    "critical_path": (tool_critical_path, "Longest chain of unfinished work through task dependencies, in story points.",
                      {"type": "object", "properties": {}}),
    "team_workload": (tool_team_workload, "Open story points per person against sprint capacity.",
                      {"type": "object", "properties": {}}),
    "sprint_summary": (tool_sprint_summary, "Everything needed for a status report: progress, risks, critical path and recent changes.",
                       {"type": "object", "properties": {}}),
}


# ---------------------------------------------------------------- JSON-RPC over stdio
def reply(msg_id, result=None, error=None) -> None:
    out = {"jsonrpc": "2.0", "id": msg_id}
    out["error" if error else "result"] = error or result
    sys.stdout.write(json.dumps(out) + "\n")
    sys.stdout.flush()


def handle(msg: dict) -> None:
    method, msg_id, params = msg.get("method"), msg.get("id"), msg.get("params") or {}
    if msg_id is None:  # notification, e.g. notifications/initialized
        return
    if method == "initialize":
        reply(msg_id, {"protocolVersion": params.get("protocolVersion", PROTOCOL_VERSION),
                       "capabilities": {"tools": {}},
                       "serverInfo": {"name": "mustang-rover-board", "version": "1.0.0"}})
    elif method == "ping":
        reply(msg_id, {})
    elif method == "tools/list":
        reply(msg_id, {"tools": [{"name": n, "description": d, "inputSchema": s}
                                 for n, (_, d, s) in TOOLS.items()]})
    elif method == "tools/call":
        name = params.get("name")
        if name not in TOOLS:
            reply(msg_id, error={"code": -32602, "message": f"Unknown tool {name}"})
            return
        try:
            data = TOOLS[name][0](params.get("arguments") or {})
            reply(msg_id, {"content": [{"type": "text", "text": json.dumps(data, indent=2)}]})
        except Exception as exc:  # tool errors go back to the model, not the transport
            reply(msg_id, {"content": [{"type": "text", "text": f"Error: {exc}"}], "isError": True})
    else:
        reply(msg_id, error={"code": -32601, "message": f"Method not found: {method}"})


def main() -> None:
    if "--reset" in sys.argv:
        reset_board()
        print(f"Board reset: {BOARD}", file=sys.stderr)
        return
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            handle(json.loads(line))
        except json.JSONDecodeError:
            reply(None, error={"code": -32700, "message": "Parse error"})


if __name__ == "__main__":
    main()
