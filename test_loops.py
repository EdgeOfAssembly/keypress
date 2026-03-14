#!/usr/bin/env python3
"""
Unit tests for expand_script_loops() in keypress.py.

These tests exercise loop parsing and expansion without requiring an X11
display, so they can run in any CI environment.
"""

import sys
import os
import subprocess

# We import expand_script_loops directly; it has no X11 dependency.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import only the pure function – avoids triggering the Xlib import at
# module level.  We do a targeted exec-style import so this file stays
# usable in environments without python3-xlib installed.
import importlib.util
import types

_spec = importlib.util.spec_from_file_location(
    "keypress_module",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "keypress.py"),
)
_mod = types.ModuleType(_spec.name)

# Stub out Xlib before the module body runs so the import doesn't fail
# in headless environments that lack python3-xlib.
try:
    import Xlib  # noqa: F401 - already available in CI
    _spec.loader.exec_module(_mod)
except ImportError:
    # Provide minimal stubs so the module-level code can be parsed.
    import unittest.mock as _mock
    sys.modules.setdefault("Xlib", _mock.MagicMock())
    sys.modules.setdefault("Xlib.X", _mock.MagicMock())
    sys.modules.setdefault("Xlib.display", _mock.MagicMock())
    sys.modules.setdefault("Xlib.XK", _mock.MagicMock())
    sys.modules.setdefault("Xlib.ext", _mock.MagicMock())
    sys.modules.setdefault("Xlib.ext.xtest", _mock.MagicMock())
    _spec.loader.exec_module(_mod)

expand_script_loops = _mod.expand_script_loops

PASS = 0
FAIL = 0


def ok(name):
    global PASS
    PASS += 1
    print(f"  ✅ {name}")


def fail(name, detail=""):
    global FAIL
    FAIL += 1
    msg = f"  ❌ {name}"
    if detail:
        msg += f": {detail}"
    print(msg)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def lines(*args):
    """Turn bare strings into lines (each ending with \\n) as readlines() would."""
    return [a + "\n" for a in args]


def run_expect_exit(test_lines):
    """Return True if expand_script_loops raises SystemExit (as expected on errors)."""
    try:
        expand_script_loops(test_lines)
        return False
    except SystemExit:
        return True


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

print("=== Loop expansion tests ===")

# 1. Simple loop – body repeated N times
result = expand_script_loops(lines("<for:3>", "hello", "</for>"))
expected = lines("hello", "hello", "hello")
if result == expected:
    ok("Simple <for:3> repeats body 3 times")
else:
    fail("Simple <for:3> repeats body 3 times", f"got {result!r}")

# 2. Loop count 1 – body appears exactly once
result = expand_script_loops(lines("<for:1>", "once", "</for>"))
if result == lines("once"):
    ok("<for:1> produces body exactly once")
else:
    fail("<for:1> produces body exactly once", f"got {result!r}")

# 3. Multi-line body
result = expand_script_loops(lines("<for:2>", "<Tab>", "<Enter>", "</for>"))
expected = lines("<Tab>", "<Enter>", "<Tab>", "<Enter>")
if result == expected:
    ok("Multi-line body is fully repeated")
else:
    fail("Multi-line body is fully repeated", f"got {result!r}")

# 4. Surrounding non-loop lines are preserved
result = expand_script_loops(lines("before", "<for:2>", "x", "</for>", "after"))
expected = lines("before", "x", "x", "after")
if result == expected:
    ok("Lines outside loop are preserved")
else:
    fail("Lines outside loop are preserved", f"got {result!r}")

# 5. Nested loops
result = expand_script_loops(lines("<for:2>", "<for:3>", "a", "</for>", "</for>"))
expected = lines(*["a"] * 6)
if result == expected:
    ok("Nested <for:2><for:3> produces 6 repetitions")
else:
    fail("Nested <for:2><for:3> produces 6 repetitions", f"got {result!r}")

# 6. Case-insensitive tags
result = expand_script_loops(["<FOR:2>\n", "hi\n", "</FOR>\n"])
if result == lines("hi", "hi"):
    ok("<FOR:2> / </FOR> tags are case-insensitive")
else:
    fail("<FOR:2> / </FOR> tags are case-insensitive", f"got {result!r}")

# 7. Loop count 0 must fail
if run_expect_exit(lines("<for:0>", "x", "</for>")):
    ok("<for:0> is rejected with exit")
else:
    fail("<for:0> is rejected with exit")

# 8. Negative count must fail
if run_expect_exit(lines("<for:-1>", "x", "</for>")):
    ok("<for:-1> is rejected with exit")
else:
    fail("<for:-1> is rejected with exit")

# 9. Non-integer count must fail
if run_expect_exit(lines("<for:abc>", "x", "</for>")):
    ok("<for:abc> is rejected with exit")
else:
    fail("<for:abc> is rejected with exit")

# 10. Float count must fail
if run_expect_exit(lines("<for:1.5>", "x", "</for>")):
    ok("<for:1.5> is rejected with exit")
else:
    fail("<for:1.5> is rejected with exit")

# 11. Missing </for> must fail
if run_expect_exit(lines("<for:2>", "x")):
    ok("Missing </for> is rejected with exit")
else:
    fail("Missing </for> is rejected with exit")

# 12. Stray </for> must fail
if run_expect_exit(lines("x", "</for>")):
    ok("Stray </for> with no opener is rejected with exit")
else:
    fail("Stray </for> with no opener is rejected with exit")

# 13. Empty body is valid (loop produces nothing)
result = expand_script_loops(lines("<for:5>", "</for>"))
if result == []:
    ok("<for:5> with empty body expands to nothing")
else:
    fail("<for:5> with empty body expands to nothing", f"got {result!r}")

# 14. Comments inside loop body are preserved (not stripped by expand)
result = expand_script_loops(lines("<for:2>", "# comment", "cmd", "</for>"))
expected = lines("# comment", "cmd", "# comment", "cmd")
if result == expected:
    ok("Comment lines inside loop body are preserved")
else:
    fail("Comment lines inside loop body are preserved", f"got {result!r}")

# 15. Plain script without any loops is returned unchanged
plain = lines("hello", "<Tab>", "<wait:1>", "world")
result = expand_script_loops(plain)
if result == plain:
    ok("Plain script without loops is returned unchanged")
else:
    fail("Plain script without loops is returned unchanged", f"got {result!r}")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print()
print(f"Results: {PASS} passed, {FAIL} failed")
if FAIL:
    sys.exit(1)
else:
    print("All loop tests passed! ✅")
