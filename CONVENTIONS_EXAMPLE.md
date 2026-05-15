# Coding Conventions

These rules apply to all code the agent writes. The reviewer checks the
diff against them — a violation is grounds for REJECTED.

- Python 3.9+, standard library only — no `pip` / external dependencies.
- Must pass `python -m py_compile` (no syntax errors, no debug `print` left in library code).
- Type hints on every function signature (parameters and return).
- Functions ≤ 40 lines; one clear responsibility each.
- Names: `snake_case` for functions/variables, `UPPER_SNAKE` for constants, `CapWords` for classes.
- Handle expected errors explicitly (missing file, bad input) with a clear message; never use bare `except:`.
- No hardcoded absolute paths; build paths from arguments or the current directory.
- Keep the diff minimal and scoped to the current task — no unrelated refactors or reformatting.
- Never run global package installs (npm install -g, pip install --user, brew install, etc.); work only with project-local dependencies.
- Comment only non-obvious decisions; do not restate what the code already says.
- Follow PEP 8 (4-space indent, ≤ 100 columns).
