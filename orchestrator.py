import subprocess
import json
import os
import sys
import tempfile
import re

STATE_FILE = ".agent_state.json"
CONVENTIONS_FILE = "CONVENTIONS.md"
HISTORY_FILE = "PROGRESS.md"
REQUIREMENTS_FILE = "NEW_PROJECT.md"


def atomic_write_json(filepath: str, data: dict):
    dir_ = os.path.dirname(os.path.abspath(filepath))
    fd, tmp_filename = tempfile.mkstemp(dir=dir_, prefix=".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_filename, filepath)
    except Exception:
        try:
            os.unlink(tmp_filename)
        except OSError:
            pass
        raise


def clean_json(raw_string: str) -> str:
    match = re.search(r"```(?:json)?\s*(.*?)```", raw_string, re.DOTALL)
    if match:
        return match.group(1).strip()
    return raw_string.strip()


def ensure_sterile_workspace():
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
    )
    if result.stdout.strip():
        print(
            "Workspace is not clean. Please commit/stash your changes.",
            file=sys.stderr,
        )
        sys.exit(1)


def rollback_workspace():
    subprocess.run(["git", "reset", "--hard", "HEAD"])
    subprocess.run(["git", "clean", "-fd"])


def get_efficient_diff() -> str:
    subprocess.run(["git", "add", "-N", "."])
    result = subprocess.run(
        ["git", "diff", "-M", "-U10"],
        capture_output=True,
        text=True,
    )
    return result.stdout


def get_changed_python_files() -> list:
    """Return the changed Python files the lint step must compile.

    Covers staged, unstaged, and untracked changes. Renames resolve to
    the new path; deleted files are excluded because they cannot be
    compiled.
    """
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
    )
    files = []
    for line in result.stdout.splitlines():
        # Porcelain v1 format: 2 status chars + space + path.
        path = line[3:].strip()
        if " -> " in path:  # rename/copy: "old -> new"
            path = path.split(" -> ", 1)[1]
        path = path.strip('"')
        if path.endswith(".py") and os.path.isfile(path) and path not in files:
            files.append(path)
    return files


def run_claude(
    prompt,
    allowed_tools=None,
    requires_json=True,
    skip_permissions=False,
    max_retries=2,
    timeout=120,
):
    env = os.environ.copy()
    env["NO_COLOR"] = "1"
    env["TERM"] = "dumb"
    env["CI"] = "1"
    env["NONINTERACTIVE"] = "1"

    current_prompt = prompt

    for attempt in range(max_retries + 1):
        cmd = ["claude", "-p", current_prompt]
        if allowed_tools:
            cmd += ["--allowedTools", allowed_tools]
        if skip_permissions:
            cmd.append("--dangerously-skip-permissions")
        if os.path.exists(CONVENTIONS_FILE):
            cmd += ["--append-system-prompt-file", CONVENTIONS_FILE]
        if requires_json:
            cmd += ["--output-format", "json"]

        with tempfile.TemporaryFile() as f_out, tempfile.TemporaryFile() as f_err:
            try:
                result = subprocess.run(
                    cmd,
                    stdout=f_out,
                    stderr=f_err,
                    timeout=timeout,
                    env=env,
                )
            except subprocess.TimeoutExpired:
                return None

            f_out.seek(0)
            f_err.seek(0)
            stdout = f_out.read().decode("utf-8", errors="replace")
            stderr = f_err.read().decode("utf-8", errors="replace")

        if result.returncode != 0:
            print(stderr, file=sys.stderr)
            sys.exit(1)

        if not requires_json:
            return stdout

        try:
            return json.loads(clean_json(stdout))
        except json.JSONDecodeError as e:
            if attempt >= max_retries:
                return None
            current_prompt += (
                f"\n\n[SYSTEM] Your previous response was not valid JSON "
                f"({e}). Respond with ONLY a valid JSON object. "
                f"BE MORE CONCISE!"
            )

    return None


def get_recent_history(max_lines=15):
    if not os.path.exists(HISTORY_FILE):
        return ""
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    return "".join(lines[-max_lines:])


def step_plan():
    ensure_sterile_workspace()

    history = get_recent_history()
    prompt = (
        f"Read the project requirements in {REQUIREMENTS_FILE}.\n\n"
        f"Progress so far (most recent entries):\n{history}\n\n"
        f"Determine the next atomic task. Respond with ONLY "
        f'JSON: {{"title": "...", "description": "..."}}.'
    )

    result = run_claude(prompt, allowed_tools="Read", timeout=60)
    if not result:
        print("Planning failed (no valid result).", file=sys.stderr)
        sys.exit(1)

    state = {
        "title": result.get("title", ""),
        "description": result.get("description", ""),
        "status": "planned",
        "attempts": 0,
        "total_iterations": 0,
        "feedback": "",
    }
    atomic_write_json(STATE_FILE, state)
    print(f"Planned: {state['title']}")


def step_implement():
    if not os.path.exists(STATE_FILE):
        print("No state found. Run 'plan' first.", file=sys.stderr)
        sys.exit(1)
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        state = json.load(f)

    total_iterations = state.get("total_iterations", 0)
    if total_iterations > 15:
        print(
            "Circuit breaker: total_iterations > 15. Aborting.",
            file=sys.stderr,
        )
        sys.exit(1)
    total_iterations += 1

    attempts = state.get("attempts", 0) + 1
    if attempts > 3:
        rollback_workspace()
        attempts = 1

    state["attempts"] = attempts
    state["total_iterations"] = total_iterations

    feedback = state.get("feedback", "")
    prompt = (
        f"Fully implement the following task in the workspace:\n\n"
        f"TITLE: {state.get('title', '')}\n"
        f"DESCRIPTION: {state.get('description', '')}\n\n"
        f"FEEDBACK FROM PREVIOUS REVIEW (if present, you MUST "
        f"address it):\n{feedback}\n\n"
        f"Apply the changes directly."
    )

    result = run_claude(
        prompt,
        allowed_tools="Read,Edit,Bash",
        requires_json=False,
        skip_permissions=True,
        timeout=400,
    )

    if result is None:
        atomic_write_json(STATE_FILE, state)
        print(
            "Implement step failed (timeout). State persisted.",
            file=sys.stderr,
        )
        sys.exit(1)

    state["status"] = "needs_review"
    atomic_write_json(STATE_FILE, state)
    print("Implementation complete, ready for review.")


def step_review():
    if not os.path.exists(STATE_FILE):
        print("No state found. Run 'plan' first.", file=sys.stderr)
        sys.exit(1)
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        state = json.load(f)

    # Lint before review: compile the Python files that actually changed,
    # using the running interpreter (sys.executable) rather than a bare
    # "python", which may not be on PATH. No Python changes -> nothing to
    # lint, which is not a failure.
    py_files = get_changed_python_files()
    if py_files:
        lint = subprocess.run(
            [sys.executable, "-m", "py_compile", *py_files],
            capture_output=True,
            text=True,
        )
        if lint.returncode != 0:
            state["status"] = "needs_rework"
            state["feedback"] = f"py_compile failed:\n{lint.stderr}"
            atomic_write_json(STATE_FILE, state)
            print("Lint failed, review aborted.", file=sys.stderr)
            return
    else:
        print("No changed Python files to lint, skipping compile step.")

    diff = get_efficient_diff()
    prompt = (
        f"Review the following Git diff for correctness, completeness, "
        f"and adherence to the task.\n\n"
        f"TASK: {state.get('title', '')} - {state.get('description', '')}\n\n"
        f"DIFF:\n{diff}\n\n"
        f"Respond with ONLY JSON: "
        f'{{"status": "APPROVED or REJECTED", "feedback": "..."}}.'
    )

    result = run_claude(prompt, allowed_tools="Read", timeout=120)
    if result is None:
        print(
            "Review failed (timeout / no valid JSON).",
            file=sys.stderr,
        )
        sys.exit(1)

    status = str(result.get("status", "")).strip().upper()
    if status == "APPROVED":
        with open(HISTORY_FILE, "a", encoding="utf-8") as f:
            f.write(
                f"- {state.get('title', '')}: "
                f"{state.get('description', '')}\n"
            )
        if os.path.exists(STATE_FILE):
            os.remove(STATE_FILE)
        print("APPROVED. Task complete.")
    else:
        state["status"] = "needs_rework"
        state["feedback"] = result.get("feedback", "")
        atomic_write_json(STATE_FILE, state)
        print("REJECTED. Feedback saved.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            "Usage: python orchestrator.py [plan|implement|review]",
            file=sys.stderr,
        )
        sys.exit(1)

    command = sys.argv[1]
    if command == "plan":
        step_plan()
    elif command == "implement":
        step_implement()
    elif command == "review":
        step_review()
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)
