import subprocess
import json
import os
import sys
import tempfile
import re

STATE_FILE = ".agent_state.json"
CONVENTIONS_FILE = "CONVENTIONS.md"
HISTORY_FILE = "FORTSCHRITT.md"
REQUIREMENTS_FILE = "NEUES_PROJEKT.md"


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
            "Workspace ist nicht sauber. Bitte committen/stashen.",
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
                f"\n\n[SYSTEM] Deine vorherige Antwort war kein valides JSON "
                f"({e}). Antworte AUSSCHLIESSLICH mit einem validen "
                f"JSON-Objekt. KÜRZER FASSEN!"
            )

    return None
