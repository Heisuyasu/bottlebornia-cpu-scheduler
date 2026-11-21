# CPU Scheduling Simulator

**Group:** BOTTLEBORNIA
**Course:** Operating Systems, Final Project

A simulator for two CPU scheduling algorithms:

1. **First-Come, First-Served (FCFS)**
2. **Shortest Job First (SJF), non-preemptive**

For each run, it shows a Gantt chart, a results table (completion, turnaround, waiting and response time) and the CPU metrics (average waiting time and average turnaround time). It can be used from the terminal or from a browser.

## Requirements

- Python 3.7 or newer
- No extra packages. Everything uses the Python standard library.

## How to run

Open a terminal in this folder.

**Browser version (recommended)**

```
python web_app.py
```

The simulator opens in your browser at `http://127.0.0.1:8765`. Press `Ctrl+C` in the terminal to stop it.

**Terminal version**

```
python "python scheduler.py"
python "python scheduler.py" processes.txt
```

The quotes are needed because the file name contains a space. The second command loads a sample file at start-up.

## Files

| File | What it does |
|---|---|
| `python scheduler.py` | The simulator: process input and validation, FCFS and SJF, Gantt chart, results table and metrics. Also contains the terminal menu. |
| `web_app.py` | A small local web server that sends the browser's input to `python scheduler.py` and returns the results. It contains no scheduling logic of its own. |
| `web/index.html` | The browser interface: input form, graphical Gantt chart, time slider, per-process timeline and results tables. |
| `processes.txt` | Test case 1, where SJF beats FCFS |
| `idle_test.txt` | Test case 2, where the CPU sits idle and two processes arrive at the same time |
| `same_arrival_test.txt` | Test case 3, where every process arrives at time 0 |
| `invalid_test.txt` | Test case 4, which contains a negative arrival time to show the error handling |

## Input

For each process: **Process ID**, **arrival time**, **burst time** and **priority**.

- Times must be whole numbers. Arrival time must be 0 or more, and burst time must be 1 or more.
- Process IDs must be unique.
- Priority is collected as the project requires, but FCFS and SJF do not use it.

Input file format, one process per line (`#` starts a comment):

```
# PID  Arrival  Burst  Priority
P1     0        8      2
P2     1        4      1
```

## Formulas

| Value | Formula |
|---|---|
| Completion time (CT) | Time the process finishes |
| Turnaround time (TAT) | CT − Arrival time |
| Waiting time (WT) | TAT − Burst time |
| Response time (RT) | Start time − Arrival time |

For non-preemptive algorithms, a process runs without interruption once it starts, so its response time equals its waiting time.

## Expected results for the test files

| File | FCFS avg WT | FCFS avg TAT | SJF avg WT | SJF avg TAT |
|---|---|---|---|---|
| `processes.txt` | 8.75 | 15.25 | 7.75 | 14.25 |
| `idle_test.txt` | 1.80 | 4.40 | 1.80 | 4.40 |
| `same_arrival_test.txt` | 7.50 | 12.25 | 4.50 | 9.25 |
