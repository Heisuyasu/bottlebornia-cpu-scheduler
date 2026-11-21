"""
CPU Scheduling Algorithm Simulator
==================================
Group: BOTTLEBORNIA (Operating Systems final project)

Simulates two CPU scheduling algorithms:

    1. First-Come, First-Served (FCFS)
    2. Shortest Job First (SJF) - Non-preemptive

Features
--------
* Processes can be typed in or loaded from a text file.
* Every field is validated (no negative times, no missing fields,
  no duplicate Process IDs, burst time must be > 0, ...).
* Output: text-based Gantt chart, results table, and CPU metrics
  (average waiting time and average turnaround time).
* A "compare" option runs both algorithms on the same data.

Usage
-----
    python "python scheduler.py"                 # interactive menu
    python "python scheduler.py" processes.txt   # preload processes from a file
    python web_app.py                            # same simulator in the browser

(The quotes are needed because the file name contains a space.)

Input file format (one process per line; '#' starts a comment):
    # PID  Arrival  Burst  Priority
    P1     0        8      2
    P2     1        4      1

Note: Priority is collected because the project requires it, but FCFS and
SJF do not use it. It is stored so a Priority algorithm can be added later.
"""

import sys
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class Process:
    """A single process and the values the scheduler computes for it."""
    pid: str
    arrival: int
    burst: int
    priority: int
    start: int = -1        # time the process first gets the CPU
    completion: int = -1   # time the process finishes
    waiting: int = 0       # turnaround - burst
    turnaround: int = 0    # completion - arrival
    response: int = 0      # start - arrival


class InputError(ValueError):
    """Raised when the user supplies invalid process data."""


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------
def parse_int(text, field_name, minimum):
    """Convert text to an integer and make sure it is >= minimum."""
    text = str(text).strip()
    if text == "":
        raise InputError(f"{field_name} is missing.")
    try:
        value = int(text)
    except ValueError:
        raise InputError(f"{field_name} must be a whole number (got '{text}').")
    if value < minimum:
        raise InputError(f"{field_name} must be at least {minimum} (got {value}).")
    return value


def validate_pid(pid, existing_pids):
    """Process ID must be non-empty and unique."""
    pid = pid.strip()
    if pid == "":
        raise InputError("Process ID is missing.")
    if pid.upper() in (p.upper() for p in existing_pids):
        raise InputError(f"Process ID '{pid}' is already used.")
    return pid


def build_process(pid, arrival, burst, priority, existing_pids):
    """Validate all four fields and return a Process object."""
    return Process(
        pid=validate_pid(pid, existing_pids),
        arrival=parse_int(arrival, "Arrival time", 0),
        burst=parse_int(burst, "Burst time", 1),
        priority=parse_int(priority, "Priority", 0),
    )


# ---------------------------------------------------------------------------
# Input: keyboard and file
# ---------------------------------------------------------------------------
def prompt_field(label, validator):
    """Keep asking until the validator accepts the input."""
    while True:
        try:
            return validator(input(label))
        except InputError as err:
            print(f"  [Invalid input] {err} Please try again.")


def read_processes_from_keyboard():
    """Ask the user for the number of processes and each process's data."""
    count = prompt_field("Number of processes: ",
                         lambda t: parse_int(t, "Number of processes", 1))
    processes = []
    for i in range(1, count + 1):
        print(f"\n--- Process {i} of {count} ---")
        pids = [p.pid for p in processes]
        pid = prompt_field("  Process ID (e.g. P1)  : ",
                           lambda t: validate_pid(t, pids))
        arrival = prompt_field("  Arrival time          : ",
                               lambda t: parse_int(t, "Arrival time", 0))
        burst = prompt_field("  Burst time            : ",
                             lambda t: parse_int(t, "Burst time", 1))
        priority = prompt_field("  Priority (lower=higher): ",
                                lambda t: parse_int(t, "Priority", 0))
        processes.append(Process(pid, arrival, burst, priority))
    return processes


def read_processes_from_file(path):
    """Load processes from a text file. Raises InputError on any problem."""
    try:
        with open(path, "r") as handle:
            lines = handle.readlines()
    except OSError as err:
        raise InputError(f"Cannot open file '{path}': {err.strerror}.")
    return parse_process_lines(lines)


def parse_process_lines(lines):
    """Turn lines of 'PID Arrival Burst Priority' text into Process objects.
    Shared by the file loader and the web interface. Raises InputError."""
    processes = []
    for number, raw in enumerate(lines, start=1):
        line = raw.split("#")[0].strip()          # drop comments / blank lines
        if not line:
            continue
        parts = line.replace(",", " ").split()
        if parts[0].lower() in ("pid", "process", "id"):   # optional header row
            continue
        if len(parts) != 4:
            raise InputError(f"Line {number}: expected 4 fields "
                             f"(PID Arrival Burst Priority), found {len(parts)}.")
        try:
            processes.append(build_process(*parts, [p.pid for p in processes]))
        except InputError as err:
            raise InputError(f"Line {number}: {err}")
    if not processes:
        raise InputError("The file contains no processes.")
    return processes


# ---------------------------------------------------------------------------
# Scheduling algorithms
# Each returns (finished_processes, gantt) where gantt is a list of
# (label, start_time, end_time) segments. Idle CPU time is labelled "Idle".
# ---------------------------------------------------------------------------
def copy_processes(processes):
    """Return fresh copies so one algorithm never affects another."""
    return [Process(p.pid, p.arrival, p.burst, p.priority) for p in processes]


def run_process(proc, clock, gantt):
    """Give the CPU to `proc` starting at `clock`; record its times.
    Returns the new clock value (when the process finishes)."""
    proc.start = clock
    proc.completion = clock + proc.burst
    proc.turnaround = proc.completion - proc.arrival
    proc.waiting = proc.turnaround - proc.burst
    proc.response = proc.start - proc.arrival
    gantt.append((proc.pid, proc.start, proc.completion))
    return proc.completion


def add_idle_if_needed(clock, next_arrival, gantt):
    """If the CPU has nothing to run, record an Idle block and jump ahead."""
    if next_arrival > clock:
        gantt.append(("Idle", clock, next_arrival))
        return next_arrival
    return clock


def fcfs(processes):
    """
    First-Come, First-Served.
    Processes run in order of arrival time. Ties are broken by the order
    in which they were entered (Python's sort is stable).
    """
    procs = copy_processes(processes)
    queue = sorted(procs, key=lambda p: p.arrival)
    gantt, clock = [], 0
    for proc in queue:
        clock = add_idle_if_needed(clock, proc.arrival, gantt)
        clock = run_process(proc, clock, gantt)
    return procs, gantt


def sjf(processes):
    """
    Shortest Job First (non-preemptive).
    Whenever the CPU becomes free, choose the arrived process with the
    smallest burst time. Ties: earlier arrival first, then entry order.
    Once a process starts it runs to completion.
    """
    procs = copy_processes(processes)
    remaining = list(procs)
    gantt, clock = [], 0
    while remaining:
        ready = [p for p in remaining if p.arrival <= clock]
        if not ready:                                   # CPU idle until next arrival
            clock = add_idle_if_needed(
                clock, min(p.arrival for p in remaining), gantt)
            continue
        chosen = min(ready, key=lambda p: (p.burst, p.arrival))
        remaining.remove(chosen)
        clock = run_process(chosen, clock, gantt)
    return procs, gantt


ALGORITHMS = {
    "1": ("First-Come, First-Served (FCFS)", fcfs),
    "2": ("Shortest Job First (SJF) - Non-preemptive", sjf),
}


# ---------------------------------------------------------------------------
# Output: Gantt chart, table, metrics
# ---------------------------------------------------------------------------
def merge_gantt(gantt):
    """Join consecutive Idle blocks (not needed for normal runs, kept safe)."""
    merged = []
    for label, start, end in gantt:
        if merged and merged[-1][0] == label == "Idle" and merged[-1][2] == start:
            merged[-1] = (label, merged[-1][1], end)
        else:
            merged.append((label, start, end))
    return merged


def format_gantt(gantt):
    """Build a two-line text Gantt chart: process blocks, then time marks."""
    gantt = merge_gantt(gantt)
    bar, times = "|", ""
    for label, start, end in gantt:
        width = max(len(label) + 2, 6)           # each block is at least 6 wide
        cell = label.center(width)
        bar += cell + "|"
        times += str(start).ljust(width + 1)
    times += str(gantt[-1][2])
    return bar + "\n" + times


def print_gantt(gantt):
    print("\nGantt Chart:")
    print(format_gantt(gantt))


def print_table(procs):
    """Print the per-process results table (sorted by Process ID as entered)."""
    header = (f"{'PID':<6}{'Arrival':>8}{'Burst':>7}{'Priority':>9}"
              f"{'Start':>7}{'Completion':>12}{'Waiting':>9}"
              f"{'Turnaround':>12}{'Response':>10}")
    print("\nResults Table:")
    print(header)
    print("-" * len(header))
    for p in procs:
        print(f"{p.pid:<6}{p.arrival:>8}{p.burst:>7}{p.priority:>9}"
              f"{p.start:>7}{p.completion:>12}{p.waiting:>9}"
              f"{p.turnaround:>12}{p.response:>10}")


def compute_metrics(procs):
    """Return (average waiting time, average turnaround time)."""
    n = len(procs)
    return (sum(p.waiting for p in procs) / n,
            sum(p.turnaround for p in procs) / n)


def print_metrics(procs):
    avg_wait, avg_tat = compute_metrics(procs)
    print("\nCPU Metrics:")
    print(f"  Average Waiting Time    : {avg_wait:.2f}")
    print(f"  Average Turnaround Time : {avg_tat:.2f}")


def run_and_report(name, algorithm, processes):
    """Run one algorithm and display Gantt chart, table and metrics."""
    print("\n" + "=" * 64)
    print(f"  {name}")
    print("=" * 64)
    finished, gantt = algorithm(processes)
    print_gantt(gantt)
    print_table(finished)
    print_metrics(finished)
    return finished


def compare_all(processes):
    """Run every algorithm and show a side-by-side summary."""
    summary = []
    for name, algorithm in ALGORITHMS.values():
        finished = run_and_report(name, algorithm, processes)
        summary.append((name, *compute_metrics(finished)))
    print("\n" + "=" * 64)
    print("  COMPARISON SUMMARY")
    print("=" * 64)
    print(f"{'Algorithm':<46}{'Avg WT':>9}{'Avg TAT':>9}")
    for name, wt, tat in summary:
        print(f"{name:<46}{wt:>9.2f}{tat:>9.2f}")


def show_processes(processes):
    """Display the currently loaded input."""
    print("\nCurrent processes:")
    print(f"{'PID':<6}{'Arrival':>8}{'Burst':>7}{'Priority':>9}")
    for p in processes:
        print(f"{p.pid:<6}{p.arrival:>8}{p.burst:>7}{p.priority:>9}")


# ---------------------------------------------------------------------------
# Main menu
# ---------------------------------------------------------------------------
MENU = """
==================== CPU SCHEDULING SIMULATOR ====================
                        by group BOTTLEBORNIA
------------------------------------------------------------------
  1. Run FCFS
  2. Run SJF (Non-preemptive)
  3. Compare both algorithms
  4. Enter new processes (keyboard)
  5. Load processes from file
  6. Show current processes
  0. Exit
==================================================================
"""


def main():
    processes = []
    if len(sys.argv) > 1:                       # optional file given on command line
        try:
            processes = read_processes_from_file(sys.argv[1])
            print(f"Loaded {len(processes)} process(es) from {sys.argv[1]}.")
        except InputError as err:
            print(f"[Error] {err}")

    while True:
        print(MENU)
        choice = input("Choose an option: ").strip()

        if choice in ALGORITHMS or choice == "3" or choice == "6":
            if not processes:
                print("[Error] No processes loaded. Use option 4 or 5 first.")
            elif choice == "3":
                compare_all(processes)
            elif choice == "6":
                show_processes(processes)
            else:
                name, algorithm = ALGORITHMS[choice]
                run_and_report(name, algorithm, processes)
        elif choice == "4":
            processes = read_processes_from_keyboard()
        elif choice == "5":
            try:
                processes = read_processes_from_file(input("File path: ").strip())
                print(f"Loaded {len(processes)} process(es).")
            except InputError as err:
                print(f"[Error] {err}")
        elif choice == "0":
            print("Goodbye!")
            break
        else:
            print("[Invalid option] Please choose 0-6.")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nExiting.")
