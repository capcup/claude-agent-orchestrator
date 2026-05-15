# Claude Code Orchestrator

A reusable, robust, and deterministic Python wrapper around the "Claude Code" CLI.

## Paradigm

- **Headless execution:** No interactive operation – the orchestrator is invoked entirely through scripts.
- **Defensive programming:** Every step is guarded against crashes, hallucinations, and malformed LLM output.
- **Absolute OS and Git safety:** The workspace state is checked before every step; atomic writes prevent corrupted state files.
- **Persistence in Git:** Progress and state are stored under version control.

## Requirements

- Python 3.9+
- Claude Code CLI (`claude`) installed on `PATH` and authenticated
- Git installed

## Usage

```bash
# Plan the next atomic task
python orchestrator.py plan

# Implement the task
python orchestrator.py implement

# Review the implementation
python orchestrator.py review
```

## Workflow

The orchestrator runs as a state machine with three steps:

1. **plan** – Reads the requirements (`NEW_PROJECT.md`) and conventions (`CONVENTIONS.md`), determines the next atomic task, and persists the state.
2. **implement** – Executes the planned task. Includes a circuit breaker (max. 15 iterations) and an automatic Git rollback after 3 failed attempts.
3. **review** – Compiles the changed Python files, inspects the diff, and decides APPROVED/REJECTED. On success, `PROGRESS.md` is updated.

## Configuration files

| File | Purpose |
|---|---|
| `NEW_PROJECT.md` | Requirements and task description for the current project |
| `CONVENTIONS.md` | Coding conventions appended to the LLM as a system prompt |
| `PROGRESS.md` | Progress log – appended automatically on every APPROVED review |
| `.agent_state.json` | Transient state between steps (not committed) |

## Python standard library only

No external dependencies. Requires: `subprocess`, `json`, `os`, `sys`, `tempfile`, `re`.
