# Project: <name>

Replace the example below with your own project. The `plan` step reads this
file plus the recent `PROGRESS.md` entries and picks the *next single
unfinished* item from "Requirements". Keep requirements small and atomic so
each plan/implement/review cycle stays within the timeouts.

## Goal

One or two sentences describing what to build and why.

## Tech constraints

- Language / runtime: Python 3.9+
- Dependencies: standard library only (no pip installs)
- Entry point file: `todo.py`
- Style: PEP 8, type hints, must pass `python -m py_compile`

## Requirements

Work top to bottom; each line should be one atomic, independently
reviewable task.

- [ ] Create `todo.py` with an `argparse` CLI and an `add <text>` command that appends a task to `tasks.json`
- [ ] Add a `list` command that prints all tasks with their index and status
- [ ] Add a `done <index>` command that marks a task as completed
- [ ] Add a `rm <index>` command that deletes a task
- [ ] Add basic error handling (missing file, invalid index) with clear messages

## Definition of done (per task)

- Code compiles (`py_compile` passes)
- The new behavior works when invoked from the CLI
- No regressions to previously completed requirements
- Changes are minimal and scoped to the current task only

## Out of scope

- Networking, databases, external services
- GUI / web frontend
- Anything not listed under "Requirements"
