"""
CPU Scheduling Simulator - Browser Interface
============================================
Group: BOTTLEBORNIA (Operating Systems final project)

Runs a small local web server so the simulator can be used from a browser
with a graphical Gantt chart, results table and metric cards.

All scheduling logic (FCFS, SJF, validation, metrics) comes from
python scheduler.py. This file only moves data between that module and the
web page in web/index.html. It uses the Python standard library only,
so nothing needs to be installed.

Usage
-----
    python web_app.py

The browser opens automatically at http://127.0.0.1:8765
(the next free port is used if 8765 is busy). Press Ctrl+C to stop.
"""

import importlib.util
import json
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE = os.path.join(HERE, "web", "index.html")
HOST = "127.0.0.1"
FIRST_PORT = 8765


# ---------------------------------------------------------------------------
# Load the scheduling engine from "python scheduler.py"
# (the space in the file name means a normal "import" cannot be used)
# ---------------------------------------------------------------------------
def load_engine():
    path = os.path.join(HERE, "python scheduler.py")
    spec = importlib.util.spec_from_file_location("cpu_scheduling", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["cpu_scheduling"] = module       # needed for @dataclass
    spec.loader.exec_module(module)
    return module


engine = load_engine()

# Which engine function runs for each choice on the web page
WEB_ALGORITHMS = {
    "fcfs": engine.ALGORITHMS["1"],
    "sjf": engine.ALGORITHMS["2"],
}


# ---------------------------------------------------------------------------
# Validation: check every field of every row and report all problems at once
# ---------------------------------------------------------------------------
def validate_rows(rows):
    """Return (processes, errors). Each error names the row and field."""
    if not isinstance(rows, list) or not rows:
        return [], [{"row": None, "field": None,
                     "message": "Add at least one process."}]

    checks = (
        ("arrival", "Arrival time", 0),
        ("burst", "Burst time", 1),
        ("priority", "Priority", 0),
    )
    processes, errors, seen_pids = [], [], []
    for index, row in enumerate(rows):
        row = row if isinstance(row, dict) else {}
        values = {}
        try:
            values["pid"] = engine.validate_pid(str(row.get("pid", "")), seen_pids)
            seen_pids.append(values["pid"])
        except engine.InputError as err:
            errors.append({"row": index, "field": "pid", "message": str(err)})
        for key, label, minimum in checks:
            try:
                values[key] = engine.parse_int(row.get(key, ""), label, minimum)
            except engine.InputError as err:
                errors.append({"row": index, "field": key, "message": str(err)})
        if len(values) == 4:
            processes.append(engine.Process(values["pid"], values["arrival"],
                                            values["burst"], values["priority"]))
    return processes, errors


# ---------------------------------------------------------------------------
# Run an algorithm and package the results for the web page
# ---------------------------------------------------------------------------
def schedule_to_dict(key, processes):
    name, algorithm = WEB_ALGORITHMS[key]
    finished, gantt = algorithm(processes)
    gantt = engine.merge_gantt(gantt)
    avg_wait, avg_tat = engine.compute_metrics(finished)

    total_time = gantt[-1][2] - gantt[0][1]
    busy_time = sum(end - start for label, start, end in gantt if label != "Idle")

    return {
        "key": key,
        "name": name,
        "gantt": [{"label": l, "start": s, "end": e} for l, s, e in gantt],
        "text_gantt": engine.format_gantt(gantt),
        "rows": [{
            "pid": p.pid, "arrival": p.arrival, "burst": p.burst,
            "priority": p.priority, "start": p.start,
            "completion": p.completion, "waiting": p.waiting,
            "turnaround": p.turnaround, "response": p.response,
        } for p in finished],
        "avg_waiting": round(avg_wait, 2),
        "avg_turnaround": round(avg_tat, 2),
        "avg_response": round(sum(p.response for p in finished) / len(finished), 2),
        "utilization": round(100 * busy_time / total_time, 1) if total_time else 100.0,
    }


def handle_schedule(payload):
    algorithm = payload.get("algorithm")
    keys = ["fcfs", "sjf"] if algorithm == "compare" else [algorithm]
    if any(k not in WEB_ALGORITHMS for k in keys):
        return 400, {"errors": [{"row": None, "field": None,
                                 "message": "Choose FCFS, SJF or Compare both."}]}
    processes, errors = validate_rows(payload.get("processes"))
    if errors:
        return 400, {"errors": errors}
    return 200, {"results": [schedule_to_dict(k, processes) for k in keys]}


def handle_parse(payload):
    """Read the text of an uploaded .txt file using the engine's file parser."""
    try:
        processes = engine.parse_process_lines(str(payload.get("text", "")).splitlines())
    except engine.InputError as err:
        return 400, {"errors": [{"row": None, "field": None, "message": str(err)}]}
    return 200, {"processes": [{"pid": p.pid, "arrival": p.arrival, "burst": p.burst,
                                "priority": p.priority} for p in processes]}


# ---------------------------------------------------------------------------
# HTTP server
# ---------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    routes = {"/api/schedule": handle_schedule, "/api/parse": handle_parse}

    def send_body(self, status, body, content_type):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            with open(PAGE, "r", encoding="utf-8") as handle:
                self.send_body(200, handle.read(), "text/html; charset=utf-8")
        else:
            self.send_body(404, "Not found", "text/plain; charset=utf-8")

    def do_POST(self):
        route = self.routes.get(self.path)
        if route is None:
            self.send_body(404, "Not found", "text/plain; charset=utf-8")
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(payload, dict):
                raise ValueError
        except ValueError:
            status, body = 400, {"errors": [{"row": None, "field": None,
                                             "message": "The request could not be read."}]}
        else:
            status, body = route(payload)
        self.send_body(status, json.dumps(body), "application/json")

    def log_message(self, fmt, *args):
        pass                                     # keep the terminal quiet


def start_server():
    """Try port 8765, then the next few ports if it is already in use."""
    for port in range(FIRST_PORT, FIRST_PORT + 20):
        try:
            return ThreadingHTTPServer((HOST, port), Handler), port
        except OSError:
            continue
    raise SystemExit("No free port found between 8765 and 8784.")


def main():
    server, port = start_server()
    url = f"http://{HOST}:{port}"
    print("CPU Scheduling Simulator by BOTTLEBORNIA")
    print(f"Running at {url}")
    print("Press Ctrl+C to stop.")
    if "--no-browser" not in sys.argv:
        threading.Timer(0.6, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
