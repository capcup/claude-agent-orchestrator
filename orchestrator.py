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
