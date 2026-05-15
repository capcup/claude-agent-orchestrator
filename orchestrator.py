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
        f"Lies die Projektanforderungen in {REQUIREMENTS_FILE}.\n\n"
        f"Bisheriger Fortschritt (letzte Eintraege):\n{history}\n\n"
        f"Ermittle die naechste atomare Aufgabe. Antworte AUSSCHLIESSLICH in "
        f'JSON: {{"title": "...", "description": "..."}}.'
    )

    result = run_claude(prompt, allowed_tools="Read", timeout=60)
    if not result:
        print("Planung fehlgeschlagen (kein valides Ergebnis).", file=sys.stderr)
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
    print(f"Geplant: {state['title']}")


def step_implement():
    if not os.path.exists(STATE_FILE):
        print("Kein State vorhanden. Zuerst 'plan' ausfuehren.", file=sys.stderr)
        sys.exit(1)
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        state = json.load(f)

    total_iterations = state.get("total_iterations", 0)
    if total_iterations > 15:
        print(
            "Circuit Breaker: total_iterations > 15. Abbruch.",
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
        f"Setze folgende Aufgabe vollstaendig im Workspace um:\n\n"
        f"TITEL: {state.get('title', '')}\n"
        f"BESCHREIBUNG: {state.get('description', '')}\n\n"
        f"FEEDBACK AUS VORHERIGEM REVIEW (falls vorhanden, zwingend "
        f"beheben):\n{feedback}\n\n"
        f"Implementiere die Aenderungen direkt."
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
            "Implement-Schritt fehlgeschlagen (Timeout). State persistiert.",
            file=sys.stderr,
        )
        sys.exit(1)

    state["status"] = "needs_review"
    atomic_write_json(STATE_FILE, state)
    print("Implementierung abgeschlossen, bereit fuer Review.")


def step_review():
    if not os.path.exists(STATE_FILE):
        print("Kein State vorhanden. Zuerst 'plan' ausfuehren.", file=sys.stderr)
        sys.exit(1)
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        state = json.load(f)

    lint = subprocess.run(
        ["python", "-m", "py_compile", "app.py"],
        capture_output=True,
        text=True,
    )
    if lint.returncode != 0:
        state["status"] = "needs_rework"
        state["feedback"] = f"py_compile fehlgeschlagen:\n{lint.stderr}"
        atomic_write_json(STATE_FILE, state)
        print("Lint fehlgeschlagen, Review abgebrochen.", file=sys.stderr)
        return

    diff = get_efficient_diff()
    prompt = (
        f"Pruefe den folgenden Git-Diff auf Korrektheit, Vollstaendigkeit "
        f"und Einhaltung der Aufgabe.\n\n"
        f"AUFGABE: {state.get('title', '')} - {state.get('description', '')}\n\n"
        f"DIFF:\n{diff}\n\n"
        f"Antworte AUSSCHLIESSLICH in JSON: "
        f'{{"status": "APPROVED oder REJECTED", "feedback": "..."}}.'
    )

    result = run_claude(prompt, allowed_tools="Read", timeout=120)
    if result is None:
        print(
            "Review fehlgeschlagen (Timeout/kein valides JSON).",
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
        print("APPROVED. Aufgabe abgeschlossen.")
    else:
        state["status"] = "needs_rework"
        state["feedback"] = result.get("feedback", "")
        atomic_write_json(STATE_FILE, state)
        print("REJECTED. Feedback gespeichert.")


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
        print(f"Unbekannter Befehl: {command}", file=sys.stderr)
        sys.exit(1)
