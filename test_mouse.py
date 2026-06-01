#!/usr/bin/env python3
"""
Integration tests for mouse.py – MouseAutomation class.

Exercises constructor, script command parsing, file I/O execution,
X11 fake_input event generation, and CLI argument handling.

Run with:
    python3 test_mouse.py
"""

import sys
import os
import tempfile
import subprocess
import unittest.mock as mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------
# Bootstrap: mock Xlib before importing mouse.py so the import doesn't
# fail in environments without python3-xlib.
# ---------------------------------------------------------------------------
for _name in ("Xlib", "Xlib.X", "Xlib.display", "Xlib.XK",
              "Xlib.ext", "Xlib.ext.xtest", "Xlib.protocol",
              "Xlib.protocol.event"):
    sys.modules.setdefault(_name, mock.MagicMock())

import importlib.util
import types

_spec = importlib.util.spec_from_file_location(
    "mouse_module",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "mouse.py"),
)
_mod = types.ModuleType(_spec.name)
_spec.loader.exec_module(_mod)

MouseAutomation = _mod.MouseAutomation

# ---------------------------------------------------------------------------
# PASS / FAIL framework (same pattern as test_loops.py / test_integration.py)
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


# ---------------------------------------------------------------------------
# Helper: create a MouseAutomation instance without touching __init__
# ---------------------------------------------------------------------------

def make_auto():
    auto = object.__new__(MouseAutomation)
    auto.event_delay = 0
    auto.x11 = mock.MagicMock()
    auto.controller = mock.MagicMock()
    auto.finder = mock.MagicMock()
    auto.launcher = mock.MagicMock()
    auto.window = mock.MagicMock()
    auto.window_valid = True
    auto.click_calls = []
    auto.move_calls = []
    auto.scroll_calls = []
    auto.drag_calls = []
    auto.double_click_calls = []
    auto.right_click_calls = []
    auto._click = lambda x, y, button=1: auto.click_calls.append((x, y, button))
    auto._move = lambda x, y: auto.move_calls.append((x, y))
    auto._scroll = lambda direction, amount=1: auto.scroll_calls.append((direction, amount))
    auto._drag = lambda x1, y1, x2, y2: auto.drag_calls.append((x1, y1, x2, y2))
    auto._double_click = lambda x, y: auto.double_click_calls.append((x, y))
    auto._right_click = lambda x, y: auto.right_click_calls.append((x, y))
    return auto


def make_auto_real_methods():
    """Create auto instance with real click/move/scroll/drag/double_click/right_click
    but with fake_input patched so we can verify X11 calls."""
    auto = object.__new__(MouseAutomation)
    auto.event_delay = 0
    auto.startup_delay = 0
    auto.debug = False
    auto.x11 = mock.MagicMock()
    auto.controller = mock.MagicMock()
    auto.finder = mock.MagicMock()
    auto.launcher = mock.MagicMock()
    auto.window = mock.MagicMock()
    auto.window_valid = True
    return auto


# ---------------------------------------------------------------------------
# 1. Constructor tests (2 tests)
# ---------------------------------------------------------------------------

print("=== MouseAutomation constructor tests ===")


def test_constructor_creates_instances():
    with mock.patch.object(_mod, 'X11Display', autospec=True) as MockX11, \
         mock.patch.object(_mod, 'WindowFinder', autospec=True) as MockFinder, \
         mock.patch.object(_mod, 'WindowController', autospec=True) as MockCtrl, \
         mock.patch.object(_mod, 'ProgramLauncher', autospec=True) as MockLauncher:
        auto = MouseAutomation(program_cmd="echo hi", event_delay=0.05)
        if isinstance(auto.x11, MockX11.return_value.__class__):
            ok("constructor creates x11 instance")
        else:
            fail("constructor creates x11 instance", f"x11 is {type(auto.x11)}")
        if isinstance(auto.finder, MockFinder.return_value.__class__):
            ok("constructor creates finder instance")
        else:
            fail("constructor creates finder instance", f"finder is {type(auto.finder)}")
        if isinstance(auto.controller, MockCtrl.return_value.__class__):
            ok("constructor creates controller instance")
        else:
            fail("constructor creates controller instance", f"controller is {type(auto.controller)}")
        if isinstance(auto.launcher, MockLauncher.return_value.__class__):
            ok("constructor creates launcher instance")
        else:
            fail("constructor creates launcher instance", f"launcher is {type(auto.launcher)}")


test_constructor_creates_instances()


def test_constructor_stores_params():
    with mock.patch.object(_mod, 'X11Display', autospec=True), \
         mock.patch.object(_mod, 'WindowFinder', autospec=True), \
         mock.patch.object(_mod, 'WindowController', autospec=True), \
         mock.patch.object(_mod, 'ProgramLauncher', autospec=True):
        auto = MouseAutomation(
            program_cmd="gedit",
            event_delay=0.1,
            window_name="MyWindow",
        )
        if auto.program_cmd == "gedit":
            ok("constructor stores program_cmd")
        else:
            fail("constructor stores program_cmd", f"got {auto.program_cmd!r}")
        if auto.event_delay == 0.1:
            ok("constructor stores event_delay")
        else:
            fail("constructor stores event_delay", f"got {auto.event_delay!r}")
        if auto.window_name == "MyWindow":
            ok("constructor stores window_name")
        else:
            fail("constructor stores window_name", f"got {auto.window_name!r}")


test_constructor_stores_params()

# ---------------------------------------------------------------------------
# 2. process_line() — script command parsing (9 tests)
# ---------------------------------------------------------------------------

print("\n=== process_line() script command parsing tests ===")


def test_click_parses_coordinates():
    auto = make_auto()
    # Patch click so it uses our tracker
    auto.click = auto._click
    auto.process_line("<click:100,200>")
    if auto.click_calls == [(100, 200, 1)]:
        ok("click parses coordinates")
    else:
        fail("click parses coordinates", f"got {auto.click_calls!r}")


test_click_parses_coordinates()


def test_rightclick_parses():
    auto = make_auto()
    # right_click calls click(x, y, button=3)
    with mock.patch.object(auto, 'click', autospec=True) as mock_click:
        auto.process_line("<rightclick:100,200>")
        if mock_click.call_count == 1 and mock_click.call_args == mock.call(100, 200, button=3):
            ok("rightclick parses coordinates and button=3")
        else:
            fail("rightclick parses coordinates and button=3",
                 f"calls={mock_click.call_args_list}")


test_rightclick_parses()


def test_dblclick_parses():
    auto = make_auto()
    with mock.patch.object(auto, 'double_click', autospec=True) as mock_dbl:
        auto.process_line("<dblclick:50,75>")
        if mock_dbl.call_count == 1 and mock_dbl.call_args == mock.call(50, 75):
            ok("dblclick parses coordinates and calls double_click")
        else:
            fail("dblclick parses coordinates and calls double_click",
                 f"calls={mock_dbl.call_args_list}")


test_dblclick_parses()


def test_move_parses():
    auto = make_auto()
    auto.move = auto._move
    auto.process_line("<move:300,400>")
    if auto.move_calls == [(300, 400)]:
        ok("move parses coordinates")
    else:
        fail("move parses coordinates", f"got {auto.move_calls!r}")


test_move_parses()


def test_scroll_down():
    auto = make_auto()
    with mock.patch.object(auto, 'scroll', autospec=True) as mock_scroll:
        auto.process_line("<scroll:down:3>")
        if mock_scroll.call_count == 1 and mock_scroll.call_args == mock.call('down', 3):
            ok("scroll down:3 parses direction and amount")
        else:
            fail("scroll down:3 parses direction and amount",
                 f"calls={mock_scroll.call_args_list}")


test_scroll_down()


def test_scroll_up():
    auto = make_auto()
    with mock.patch.object(auto, 'scroll', autospec=True) as mock_scroll:
        auto.process_line("<scroll:up:5>")
        if mock_scroll.call_count == 1 and mock_scroll.call_args == mock.call('up', 5):
            ok("scroll up:5 parses direction and amount")
        else:
            fail("scroll up:5 parses direction and amount",
                 f"calls={mock_scroll.call_args_list}")


test_scroll_up()


def test_wait_command():
    auto = make_auto()
    with mock.patch('time.sleep') as mock_sleep:
        auto.process_line("<wait:2>")
        called_with_2 = any(c == mock.call(2.0) for c in mock_sleep.call_args_list)
        if called_with_2:
            ok("wait:2 calls time.sleep(2.0)")
        else:
            fail("wait:2 calls time.sleep(2.0)",
                 f"sleep calls={mock_sleep.call_args_list}")


test_wait_command()


def test_comment_ignored():
    auto = make_auto()
    auto.click = auto._click
    auto.move = auto._move
    auto.process_line("# this is a comment")
    if auto.click_calls == [] and auto.move_calls == []:
        ok("comment line produces no action")
    else:
        fail("comment line produces no action",
             f"clicks={auto.click_calls} moves={auto.move_calls}")


test_comment_ignored()


def test_drag_parses():
    auto = make_auto()
    with mock.patch.object(auto, 'drag', autospec=True) as mock_drag:
        auto.process_line("<drag:100,200:500,600>")
        if mock_drag.call_count == 1 and mock_drag.call_args == mock.call(100, 200, 500, 600):
            ok("drag parses two coordinate pairs")
        else:
            fail("drag parses two coordinate pairs",
                 f"calls={mock_drag.call_args_list}")


test_drag_parses()

# ---------------------------------------------------------------------------
# 3. run_script_file() with file I/O (3 tests)
# ---------------------------------------------------------------------------

print("\n=== run_script_file() file I/O tests ===")


def test_script_file_executes_lines():
    auto = make_auto()
    auto.click = auto._click
    auto.move = auto._move
    auto.window_name = None  # skip window focus check

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("<click:10,20>\n<move:30,40>\n")
        path = f.name
    try:
        auto.run_script_file(path)
        if auto.click_calls == [(10, 20, 1)] and auto.move_calls == [(30, 40)]:
            ok("script file executes click and move commands")
        else:
            fail("script file executes click and move commands",
                 f"clicks={auto.click_calls} moves={auto.move_calls}")
    finally:
        os.unlink(path)


test_script_file_executes_lines()


def test_empty_script():
    auto = make_auto()
    auto.click = auto._click
    auto.move = auto._move
    auto.window_name = None

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("")
        path = f.name
    try:
        result = auto.run_script_file(path)
        if auto.click_calls == [] and auto.move_calls == [] and result is True:
            ok("empty script produces no actions and returns True")
        else:
            fail("empty script produces no actions and returns True",
                 f"clicks={auto.click_calls} moves={auto.move_calls} result={result}")
    finally:
        os.unlink(path)


test_empty_script()


def test_script_with_comments():
    auto = make_auto()
    auto.click = auto._click
    auto.move = auto._move
    auto.window_name = None

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("# comment line\n<click:5,10>\n# another comment\n<move:15,20>\n")
        path = f.name
    try:
        auto.run_script_file(path)
        if auto.click_calls == [(5, 10, 1)] and auto.move_calls == [(15, 20)]:
            ok("comments skipped, real commands executed")
        else:
            fail("comments skipped, real commands executed",
                 f"clicks={auto.click_calls} moves={auto.move_calls}")
    finally:
        os.unlink(path)


test_script_with_comments()

# ---------------------------------------------------------------------------
# 4. X11 event generation verification (4 tests)
# ---------------------------------------------------------------------------

print("\n=== X11 event generation tests ===")

# Use _mod.X for mock event-type constants (same object mouse.py uses)
X_mock = _mod.X


def test_click_generates_button_press_release():
    auto = make_auto_real_methods()
    mock_fake = mock.MagicMock()
    original_fake = _mod.fake_input
    _mod.fake_input = mock_fake
    try:
        with mock.patch('time.sleep'):
            auto.click(100, 200, button=1)
        calls = mock_fake.call_args_list
        press_calls = [c for c in calls if c[0][1] == X_mock.ButtonPress]
        release_calls = [c for c in calls if c[0][1] == X_mock.ButtonRelease]
        press_buttons = [c[0][2] for c in press_calls]
        release_buttons = [c[0][2] for c in release_calls]
        if len(press_calls) >= 1 and len(release_calls) >= 1 and \
           press_buttons[0] == 1 and release_buttons[0] == 1:
            ok("click generates ButtonPress(1) then ButtonRelease(1)")
        else:
            fail("click generates ButtonPress(1) then ButtonRelease(1)",
                 f"press={press_buttons} release={release_buttons} all={calls}")
    finally:
        _mod.fake_input = original_fake


test_click_generates_button_press_release()


def test_right_click_generates_button_3():
    auto = make_auto_real_methods()
    mock_fake = mock.MagicMock()
    original_fake = _mod.fake_input
    _mod.fake_input = mock_fake
    try:
        with mock.patch('time.sleep'):
            auto.click(50, 75, button=3)
        calls = mock_fake.call_args_list
        press_calls = [c for c in calls if c[0][1] == X_mock.ButtonPress]
        press_buttons = [c[0][2] for c in press_calls]
        if len(press_buttons) >= 1 and press_buttons[0] == 3:
            ok("right click generates ButtonPress(3)")
        else:
            fail("right click generates ButtonPress(3)",
                 f"press_buttons={press_buttons} all={calls}")
    finally:
        _mod.fake_input = original_fake


test_right_click_generates_button_3()


def test_scroll_down_generates_button_5():
    auto = make_auto_real_methods()
    mock_fake = mock.MagicMock()
    original_fake = _mod.fake_input
    _mod.fake_input = mock_fake
    try:
        with mock.patch('time.sleep'):
            auto.scroll('down', 1)
        calls = mock_fake.call_args_list
        press_calls = [c for c in calls if c[0][1] == X_mock.ButtonPress]
        press_buttons = [c[0][2] for c in press_calls]
        if len(press_buttons) >= 1 and press_buttons[0] == 5:
            ok("scroll down generates ButtonPress(5)")
        else:
            fail("scroll down generates ButtonPress(5)",
                 f"press_buttons={press_buttons} all={calls}")
    finally:
        _mod.fake_input = original_fake


test_scroll_down_generates_button_5()


def test_scroll_up_generates_button_4():
    auto = make_auto_real_methods()
    mock_fake = mock.MagicMock()
    original_fake = _mod.fake_input
    _mod.fake_input = mock_fake
    try:
        with mock.patch('time.sleep'):
            auto.scroll('up', 1)
        calls = mock_fake.call_args_list
        press_calls = [c for c in calls if c[0][1] == X_mock.ButtonPress]
        press_buttons = [c[0][2] for c in press_calls]
        if len(press_buttons) >= 1 and press_buttons[0] == 4:
            ok("scroll up generates ButtonPress(4)")
        else:
            fail("scroll up generates ButtonPress(4)",
                 f"press_buttons={press_buttons} all={calls}")
    finally:
        _mod.fake_input = original_fake


test_scroll_up_generates_button_4()

# ---------------------------------------------------------------------------
# 5. CLI argument tests (3 tests)
# ---------------------------------------------------------------------------

print("\n=== CLI argument tests ===")

MOUSE_PY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mouse.py")


def test_cli_help_exits_0():
    result = subprocess.run(
        [sys.executable, MOUSE_PY, '--help'],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode == 0 and 'click' in result.stdout.lower():
        ok("--help exits 0 and mentions 'click'")
    else:
        fail("--help exits 0 and mentions 'click'",
             f"rc={result.returncode} stdout={result.stdout[:200]}")


test_cli_help_exits_0()


def test_cli_missing_program_and_attach_errors():
    result = subprocess.run(
        [sys.executable, MOUSE_PY, '-c', '<click:1,2>'],
        capture_output=True, text=True, timeout=10,
    )
    # Should error because no program and no --attach
    if result.returncode != 0:
        ok("missing program and --attach produces error")
    else:
        fail("missing program and --attach produces error",
             f"rc={result.returncode}")


test_cli_missing_program_and_attach_errors()


def test_cli_missing_script_and_command_errors():
    result = subprocess.run(
        [sys.executable, MOUSE_PY, '--attach', '1'],
        capture_output=True, text=True, timeout=10,
    )
    # Should error because no script file or -c command
    if result.returncode != 0:
        ok("missing script and -c command produces error")
    else:
        fail("missing script and -c command produces error",
             f"rc={result.returncode}")


test_cli_missing_script_and_command_errors()

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print()
print(f"Results: {PASS} passed, {FAIL} failed")
if FAIL:
    sys.exit(1)
else:
    print("All mouse integration tests passed! \u2705")