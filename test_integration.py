#!/usr/bin/env python3
"""
Integration tests for the <for:N> / </for> loop feature in keypress.py.

These tests exercise the *full* run_script_file() execution path -- from
reading a real script file on disk, through expand_script_loops(), to the
per-line dispatch via process_line() -- without requiring a live X11 display.

Only the low-level X11 primitives (type_text, press_key, focus, send_combo,
_get_keycode) are replaced by lightweight unittest.mock stubs so that
assertion counts are unambiguous.

Run with:
    python3 test_integration.py
"""

import sys
import os
import tempfile
import unittest.mock as mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------
# Bootstrap: mock Xlib before importing keypress.py so the import doesn't
# fail in environments without python3-xlib.
# ---------------------------------------------------------------------------
try:
    import Xlib  # noqa: F401 – already installed in CI
except ImportError:
    _xmock = mock.MagicMock()
    for _name in ("Xlib", "Xlib.X", "Xlib.display", "Xlib.XK",
                  "Xlib.ext", "Xlib.ext.xtest"):
        sys.modules.setdefault(_name, _xmock)

import importlib.util
import types

_spec = importlib.util.spec_from_file_location(
    "keypress_module",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "keypress.py"),
)
_mod = types.ModuleType(_spec.name)
_spec.loader.exec_module(_mod)

KeypressAutomation = _mod.KeypressAutomation

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PASS = 0
FAIL = 0


def ok(name):
    global PASS
    PASS += 1
    print(f"  \u2705 {name}")


def fail(name, detail=""):
    global FAIL
    FAIL += 1
    msg = f"  \u274c {name}"
    if detail:
        msg += f": {detail}"
    print(msg)


def make_auto():
    """
    Return a KeypressAutomation instance that bypasses __init__ so no X11
    connection is attempted.  window_valid is True so run_script_file
    proceeds past its early-return guard.
    """
    auto = object.__new__(KeypressAutomation)
    auto.program_cmd = "test"
    auto.startup_delay = 0
    auto.typing_delay = 0
    auto.window_name = None
    auto.emulator_mode = False
    auto.debug = False
    auto.display = mock.MagicMock()
    auto.process = None
    auto.window = mock.MagicMock()
    auto.window_valid = True
    auto.keymap_cache = {}
    # Stub every method that touches X11
    auto.focus = mock.MagicMock(return_value=True)
    auto.press_key = mock.MagicMock()
    auto.type_text = mock.MagicMock()
    auto.send_combo = mock.MagicMock()
    auto._get_keycode = mock.MagicMock(return_value=(36, 0))
    return auto


def run_script(content):
    """
    Write *content* to a temporary file, call run_script_file() on it, and
    return (auto, type_text_calls) where type_text_calls is the list of
    positional argument tuples passed to auto.type_text().
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(content)
        path = f.name
    try:
        auto = make_auto()
        auto.run_script_file(path)
        calls = [c.args[0] for c in auto.type_text.call_args_list]
        return auto, calls
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

print("=== Integration tests: run_script_file() with <for:N> loops ===")

# 1. The exact broken case from the bug report:
#    <for:3> / ls / </for>  →  type_text("ls") called exactly 3 times.
_, calls = run_script("<for:3>\nls\n</for>\n")
if calls == ["ls", "ls", "ls"]:
    ok("<for:3> 'ls' loop: type_text called exactly 3 times")
else:
    fail("<for:3> 'ls' loop: type_text called exactly 3 times",
         f"got {calls!r}")

# 2. Enter is pressed once per typed line (3 typed lines → 3 Enter presses).
auto, calls = run_script("<for:3>\nls\n</for>\n")
enter_calls = auto.press_key.call_count
if enter_calls == 3:
    ok("<for:3>: Enter pressed exactly 3 times (once per iteration)")
else:
    fail("<for:3>: Enter pressed exactly 3 times",
         f"got {enter_calls} press_key calls")

# 3. <for:1> – body typed exactly once.
_, calls = run_script("<for:1>\necho hi\n</for>\n")
if calls == ["echo hi"]:
    ok("<for:1> dispatches body once")
else:
    fail("<for:1> dispatches body once", f"got {calls!r}")

# 4. Multi-line loop body – every line of the body is typed on every iteration.
_, calls = run_script("<for:2>\naaa\nbbb\n</for>\n")
if calls == ["aaa", "bbb", "aaa", "bbb"]:
    ok("<for:2> multi-line body: all lines typed in order, twice")
else:
    fail("<for:2> multi-line body: all lines typed in order, twice",
         f"got {calls!r}")

# 5. Non-loop lines surrounding a loop are typed exactly once each.
_, calls = run_script("before\n<for:2>\nx\n</for>\nafter\n")
if calls == ["before", "x", "x", "after"]:
    ok("Lines outside the loop are typed once; loop body twice")
else:
    fail("Lines outside the loop are typed once; loop body twice",
         f"got {calls!r}")

# 6. Nested loops: outer=2, inner=3 → body typed 6 times.
_, calls = run_script("<for:2>\n<for:3>\nnested\n</for>\n</for>\n")
if calls == ["nested"] * 6:
    ok("Nested <for:2><for:3>: body typed 6 times")
else:
    fail("Nested <for:2><for:3>: body typed 6 times", f"got {calls!r}")

# 7. Plain script (no loops) – each line typed exactly once, in order.
_, calls = run_script("line1\nline2\nline3\n")
if calls == ["line1", "line2", "line3"]:
    ok("Plain script (no loops): lines typed once each, in order")
else:
    fail("Plain script (no loops): lines typed once each, in order",
         f"got {calls!r}")

# 8. Empty script – nothing typed.
_, calls = run_script("")
if calls == []:
    ok("Empty script: nothing typed")
else:
    fail("Empty script: nothing typed", f"got {calls!r}")

# 9. Special-key lines (<Tab>) inside a loop are NOT sent to type_text;
#    press_key is used instead.  Verify type_text count stays at zero.
auto, calls = run_script("<for:3>\n<Tab>\n</for>\n")
if calls == []:
    ok("<for:3> <Tab> loop: type_text not called (special key path used)")
else:
    fail("<for:3> <Tab> loop: type_text not called",
         f"type_text got {calls!r}")

# press_key: 3 Tab presses (no Enter for special-key lines)
tab_calls = auto.press_key.call_count
if tab_calls == 3:
    ok("<for:3> <Tab> loop: press_key called exactly 3 times")
else:
    fail("<for:3> <Tab> loop: press_key called exactly 3 times",
         f"got {tab_calls}")

# 10. Comment lines inside a loop body are skipped by process_line (not typed).
_, calls = run_script("<for:2>\n# a comment\ncmd\n</for>\n")
if calls == ["cmd", "cmd"]:
    ok("Comment lines inside loop body skipped; real command typed twice")
else:
    fail("Comment lines inside loop body skipped; real command typed twice",
         f"got {calls!r}")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print()
print(f"Results: {PASS} passed, {FAIL} failed")
if FAIL:
    sys.exit(1)
else:
    print("All integration tests passed! \u2705")
