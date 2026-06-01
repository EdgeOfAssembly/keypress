# AGENTS.md for keypress project

## Project Overview

This is the `keypress` project — a layout-aware X11 keyboard and mouse
automation suite. It was originally a single Python script
(`keypress.py`) and has been refactored into a modular suite with shared
libraries, expanded script language, comprehensive tests, and companion
tools.

## Architecture

```
keypress.py              | Main keyboard automation script
mouse.py                 | Mouse automation companion
cp_core.py               | Shared X11 library (display, window finder, focus, launcher)
script_engine.py         | Unified script execution engine (loops, vars, conditionals)
compose_cache.py         | Dead-key and compose sequence support for typing é, ñ, €, etc.
test_*.py                | Test suite (6 files, 135+ tests)
utils/dump_keymap.py     | Diagnostic tool to inspect keyboard layout
man/                     | Man pages (keypress.1, mouse.1, dump_keymap.1)
examples/                | Example scripts for different use cases
```

## Key Design Decisions

### kp_core.py
This is the shared foundation. Both `keypress.py` and `mouse.py` import
from it. It provides:
- `X11Display` — lazy X11 display connection
- `WindowFinder` — multi-strategy window search (class → role → name → PID)
- `WindowController` — focus with EWMH _NET_ACTIVE_WINDOW + retry
- `ProgramLauncher` — `shlex.split` + `os.setsid`, never `shell=True`
- `SPECIAL_KEYS` and `KEYSYM_TO_CHAR` constants

### script_engine.py
Replaces the old monolithic `process_line()` / `run_script_file()` with
a unified engine supporting:
- Variable interpolation: `${VAR}`, `${VAR:-default}`
- Conditionals: `<if:var_defined("X")>`, `<if:eq("MODE","debug")>`
- While loops: `<while:timeout:10:window_exists("dialog")>`
- Clipboard: `<clipboard:get>`, `<clipboard:set:text>`
- Existing: `<for:N>`, `<wait:N>`, `<Ctrl+c>`, special keys

### compose_cache.py
When a character is not in the regular keyboard keymap (e.g., é, ñ, €),
this module looks up X11 Compose sequences from system Compose files
and generates the appropriate key presses. Activated automatically as
a fallback in `type_text()`.

## Backward Compatibility

All existing keypress.py scripts and CLIs must continue working.
Specifically:
- `./keypress.py "leafpad" script.txt -w leafpad` still works
- `<for:3>` syntax unchanged
- Emulator mode (`-e`) unchanged
- `expand_script_loops()` kept in keypress.py for imports

## Environment

- Target platform: X11 Linux (Wayland explicitly not supported)
- Python version: 3.6+
- Dependencies: `python3-xlib`, `xclip` (optional, for clipboard)
- Default locale context: Finnish, German, Swedish layouts supported
- Test runner: `python3 test_loops.py` etc. (no pytest dependency)

## Coding Style

- Python 3, no type hints required
- Use `try/except` around X11 calls gracefully
- Mock Xlib in tests via `sys.modules` injection
- PASS/FAIL test runner pattern with emoji indicators
- Docstrings for all public methods
- Keep the Unix philosophy: do one thing well

## Testing

Run all tests with:
```bash
python3 test_loops.py
python3 test_integration.py
python3 test_kp_core.py
python3 test_compose_cache.py
python3 test_mouse.py
python3 test_script_engine.py
```

All 6 files must pass before any commit.

## CI/CD

`.github/workflows/test.yml` runs under Ubuntu with Xvfb.
CI jobs: unit tests (no X11) + integration tests (Xvfb).

## Known Issues

- `X.INTEGER` is not exposed by python-xlib — use `AnyPropertyType` instead
- `_NET_WM_PID` is optional; some apps (feh) don't set it
- `_retry_search` catches all exceptions silently (by design for retry)

## Future Development

Planned features are documented in `docs/`:

1. `docs/IMPLEMENTATION_GUIDELINES.md` — Mandatory rules before touching `keypress.py`
2. `docs/LESSONS_LEARNED.md` — Honest autopsy of our failed refactoring attempt, with checklist
3. `docs/FEATURE_01_list_windows.md` — `--list-windows` CLI flag (standalone, safe)
4. `docs/FEATURE_02_attach.md` — `--attach` and `--attach-window-id` for existing windows
5. `docs/FEATURE_03_compose_fallback.md` — Compose sequence fallback for international chars (BLOCKED — needs deep testing)
6. `docs/FEATURE_04_script_vars.md` — `${VAR}` variable substitution in scripts (low priority)

Read `docs/LESSONS_LEARNED.md` first. Then read `docs/IMPLEMENTATION_GUIDELINES.md`.
Then pick ONE feature from the list, create a branch, implement it atomically, test it on a real display, and merge.

Under no circumstances should multiple features be implemented in the same branch without explicit justification.

