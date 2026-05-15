# Claude Code Orchestrator

A headless Python wrapper around the Claude Code CLI that autonomously plans, implements, and reviews code — task by task.

Each task goes through three steps: **plan → implement → review**. On approval the result is committed to your target directory; on rejection the reviewer's feedback is fed back into the next implement attempt automatically.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.9+ | standard library only, no pip installs needed |
| [Claude Code CLI](https://claude.ai/code) | must be on `PATH` and authenticated (`claude --version` should work) |
| Git | must be installed and on `PATH` |

---

## Setup

```bash
git clone https://github.com/capcup/claude-agent-orchestrator claude-orchestrator
cd claude-orchestrator

cp NEW_PROJECT_EXAMPLE.md NEW_PROJECT.md    # fill in your project spec
cp CONVENTIONS_EXAMPLE.md CONVENTIONS.md    # adjust coding rules (optional)
cp .env.example .env                        # set TARGET_DIR
```

**`.env`** — set where Claude should write the code:

```bash
TARGET_DIR=../my-new-project   # directory where the project will be implemented
PYTHON=python3                 # optional: path to your Python interpreter
```

The target directory is created automatically if it does not exist, and `git init` is run there if needed.

---

## Usage

```bash
./run.sh                  # implement the next 1 task
./run.sh 5                # implement the next 5 tasks in sequence
./run.sh 5 6              # 5 tasks, max 6 implement/review cycles each
```

Example output:

```
run.sh: target directory → ../my-new-project
=== Task 1/1: planning ===
Planned: Create main.py with CLI entry point
--- attempt 1/4: implement ---
--- attempt 1/4: review ---
APPROVED. Task complete.
=== Task 1 committed ===
All requested tasks done (1).
```

Run `./run.sh` again at any time — it picks up where it left off.

---

## Starting a new project

```bash
python orchestrator.py reset
```

Removes `.agent_state.json` and `PROGRESS.md`. Your code in `TARGET_DIR` is **not** touched.

Afterwards:

```bash
# replace the spec
cp NEW_PROJECT_EXAMPLE.md NEW_PROJECT.md   # or edit NEW_PROJECT.md directly

./run.sh
```

---

## Configuration files

| File | Versioned? | Purpose |
|---|---|---|
| `NEW_PROJECT_EXAMPLE.md` | Yes | Starter template — copy to `NEW_PROJECT.md` |
| `NEW_PROJECT.md` | No (gitignored) | Your project spec — what to build |
| `CONVENTIONS_EXAMPLE.md` | Yes | Starter coding rules — copy to `CONVENTIONS.md` |
| `CONVENTIONS.md` | No (gitignored) | Coding rules injected as system prompt; reviewer checks every diff against them |
| `.env` | No (gitignored) | `TARGET_DIR` and `PYTHON` |
| `PROGRESS.md` | No (gitignored) | Auto-updated log of every approved task |
| `.agent_state.json` | No (gitignored) | Transient state between steps |

---

## Manual usage

If you want to drive the steps yourself instead of using `run.sh`:

```bash
python orchestrator.py plan       # pick the next task
python orchestrator.py implement  # write the code
python orchestrator.py review     # approve or reject
python orchestrator.py reset      # clear state for a new project
```

Repeat `implement` / `review` until approved, then `git commit` in `TARGET_DIR`.

---

## Safety mechanisms

- **Sterile workspace check** — `plan` refuses to run if the target directory has uncommitted changes
- **Lint gate** — changed Python files must pass `py_compile` before a review starts
- **Circuit breaker** — aborts after 15 total implement iterations to prevent infinite loops
- **Auto rollback** — after 3 failed attempts on the same task, `git reset --hard` + `git clean -fd` resets the target directory
- **Atomic state writes** — `.agent_state.json` is written via a temp file + rename to prevent corruption
