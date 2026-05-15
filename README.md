# Claude Code Orchestrator

A headless, deterministic Python wrapper around the Claude Code CLI that autonomously plans, implements, and reviews code — task by task.

## How it works

The orchestrator runs a state machine with three steps per task:

1. **plan** — reads `NEW_PROJECT.md` and picks the next unfinished requirement as an atomic task
2. **implement** — Claude writes the code directly into the target directory
3. **review** — Claude reviews the diff; APPROVED commits the result, REJECTED feeds feedback back into the next implement attempt

`run.sh` drives this loop automatically for as many tasks as you specify.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.9+ | standard library only, no pip installs needed |
| [Claude Code CLI](https://claude.ai/code) | must be on `PATH` and authenticated (`claude --version` should work) |
| Git | must be installed and on `PATH` |

---

## Quick start

### 1. Clone this repo

```bash
git clone <this-repo> claude-orchestrator
cd claude-orchestrator
```

### 2. Describe your project

Copy the example files and fill them in:

```bash
cp NEW_PROJECT_EXAMPLE.md NEW_PROJECT.md
cp CONVENTIONS_EXAMPLE.md CONVENTIONS.md
```

`NEW_PROJECT.md` is gitignored — it holds your project-specific spec. Edit it with:

- **Goal** — one or two sentences on what to build
- **Tech constraints** — language, entry point file, style rules
- **Requirements** — a checklist of atomic tasks, one per line

`CONVENTIONS.md` is also gitignored. Adjust the coding rules to match your stack; the reviewer checks every diff against them.

Keep each requirement small enough to implement and review in a single cycle.

### 3. Set the target directory

Copy `.env.example` to `.env` and set where the generated code should be written:

```bash
cp .env.example .env
```

```bash
# .env
TARGET_DIR=../my-new-project   # where Claude writes the code
PYTHON=python3                 # optional: path to your Python interpreter
```

If `TARGET_DIR` is not set, the code is written into this repo's directory. The target directory is created automatically if it does not exist, and `git init` is run there if needed.

### 4. Run

Make the script executable (one-time):

```bash
chmod +x run.sh
```

Then run it:

```bash
./run.sh [num_tasks] [max_rework_per_task]
```

| Argument | Default | Meaning |
|---|---|---|
| `num_tasks` | `1` | How many requirements to implement in sequence |
| `max_rework_per_task` | `4` | Max implement/review cycles before giving up on a task |

`run.sh` works through the requirements in `NEW_PROJECT.md` (gitignored, not this repo) from top to bottom. It picks the next unchecked item, implements it, and commits it — then moves on to the next one.

**Example — implement the first requirement:**

```bash
./run.sh
```

```
run.sh: target directory → ../my-new-project
=== Task 1/1: planning ===
Planned: Create todo.py with argparse CLI and add command
--- attempt 1/4: implement ---
--- attempt 1/4: review ---
APPROVED. Task complete.
=== Task 1 committed ===
All requested tasks done (1).
```

**Example — implement the next 3 requirements in one go:**

```bash
./run.sh 3
```

If a task is rejected by the reviewer, `run.sh` automatically reruns `implement` with the reviewer's feedback until it is approved or the rework limit is reached. On approval, the result is committed to `TARGET_DIR` and the next task starts.

If you run `./run.sh` again later, it picks up where it left off — the next unchecked requirement in your `NEW_PROJECT.md`.

---

## Configuration files

| File | Edit? | Versioned? | Purpose |
|---|---|---|---|
| `NEW_PROJECT_EXAMPLE.md` | Template | Yes | Starter template — copy to `NEW_PROJECT.md` and fill in your spec |
| `NEW_PROJECT.md` | **Yes** | No (gitignored) | Your project requirements — what to build |
| `CONVENTIONS_EXAMPLE.md` | Template | Yes | Starter coding rules — copy to `CONVENTIONS.md` and adjust |
| `CONVENTIONS.md` | Optional | No (gitignored) | Coding rules injected as system prompt; reviewer checks diffs against them |
| `.env` | **Yes** | No (gitignored) | Local paths and interpreter (`TARGET_DIR`, `PYTHON`) |
| `PROGRESS.md` | No | No (gitignored) | Auto-updated log of every approved task |
| `.agent_state.json` | No | No (gitignored) | Transient state between steps |

---

## Safety mechanisms

- **Sterile workspace check** — `plan` refuses to run if the target directory has uncommitted changes
- **Lint gate** — changed Python files must pass `py_compile` before a review starts
- **Circuit breaker** — aborts after 15 total implement iterations to prevent infinite loops
- **Auto rollback** — after 3 failed attempts on the same task, `git reset --hard` + `git clean -fd` resets the target directory
- **Atomic state writes** — `.agent_state.json` is written via a temp file + rename to prevent corruption

---

## Manual step-by-step usage

If you want to drive the steps yourself instead of using `run.sh`:

```bash
python orchestrator.py plan       # pick the next task
python orchestrator.py implement  # write the code
python orchestrator.py review     # approve or reject
```

Repeat `implement` / `review` until approved, then `git commit` in `TARGET_DIR`.

---

## Starting a new project

To reset the orchestrator state and begin with a different spec:

```bash
python orchestrator.py reset
```

This removes `.agent_state.json` and `PROGRESS.md`. Your code in `TARGET_DIR` is not touched. Afterwards, update `NEW_PROJECT.md` with the new spec and run `plan` again.
