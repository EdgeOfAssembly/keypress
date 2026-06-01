#!/usr/bin/env python3
"""
Unit tests for kp_core.py — X11Display, WindowFinder, WindowController,
ProgramLauncher, and helper functions.

All Xlib imports are stubbed so the tests run without an X11 display.
"""

import sys
import os
import signal
import subprocess
import time
import unittest.mock as mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------
# Stub Xlib before importing kp_core
# ---------------------------------------------------------------------------
for _name in ("Xlib", "Xlib.X", "Xlib.display", "Xlib.XK",
              "Xlib.ext", "Xlib.ext.xtest", "Xlib.protocol",
              "Xlib.protocol.event"):
    sys.modules.setdefault(_name, mock.MagicMock())

import kp_core

# ---------------------------------------------------------------------------
# Test runner plumbing
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
# Helpers
# ---------------------------------------------------------------------------

def make_mock_window(wm_name=None, wm_class=None, wm_role=None,
                     window_id=12345, children=None):
    """Create a mock X11 window with configurable attributes."""
    win = mock.MagicMock()
    win.get_wm_name.return_value = wm_name
    win.get_wm_class.return_value = wm_class  # e.g. ("leafpad", "Leafpad")
    win.get_wm_window_role.return_value = wm_role
    win.id = window_id
    win.query_tree.return_value.children = children or []
    return win


# ---------------------------------------------------------------------------
# X11Display tests
# ---------------------------------------------------------------------------

print("=== X11Display tests ===")


def test_display_lazy_init():
    xd = kp_core.X11Display()
    assert xd._display is None, "Expected _display to be None before first access"

    d = xd.display  # triggers lazy init via display.Display()

    assert xd._display is not None, "Expected _display to be set after access"
    assert d is xd._display, "Property should return the same object as _display"
    ok("display property triggers lazy init on first access")


def test_get_keycode_range_fallback():
    xd = kp_core.X11Display()

    # Use spec so every attribute access raises AttributeError
    class NoKeycode:
        pass
    xd._display = mock.MagicMock(spec=NoKeycode)

    mink, maxk = xd._get_keycode_range()
    assert mink == 8, f"Expected min keycode 8, got {mink}"
    assert maxk == 255, f"Expected max keycode 255, got {maxk}"
    ok("get_keycode_range falls back to (8, 255) when all paths fail")


def test_get_keycode_range_from_attribute():
    xd = kp_core.X11Display()
    xd._display = mock.MagicMock()
    xd._display.min_keycode = 10
    xd._display.max_keycode = 200

    mink, maxk = xd._get_keycode_range()
    assert mink == 10, f"Expected min keycode 10, got {mink}"
    assert maxk == 200, f"Expected max keycode 200, got {maxk}"
    ok("get_keycode_range reads min_keycode/max_keycode from display")


def test_close_sets_none():
    xd = kp_core.X11Display()
    xd.display  # trigger lazy init
    assert xd._display is not None, "Expected _display to be set before close"

    xd.close()
    assert xd._display is None, "Expected _display to be None after close"
    ok("close() sets _display to None")


test_display_lazy_init()
test_get_keycode_range_fallback()
test_get_keycode_range_from_attribute()
test_close_sets_none()

# ---------------------------------------------------------------------------
# WindowFinder tests
# ---------------------------------------------------------------------------

print("\n=== WindowFinder tests ===")


def test_find_by_class_exact():
    """find_by_class matches WM_CLASS res_class case-insensitively."""
    root = mock.MagicMock()
    root.query_tree.return_value.children = []

    win = make_mock_window(
        wm_name="Leafpad",
        wm_class=("leafpad", "Leafpad"),
    )
    root.query_tree.return_value.children = [win]

    mock_xd = mock.MagicMock()
    wf = kp_core.WindowFinder(mock_xd, max_attempts=1, retry_sleep=0)
    result = wf.find_by_class("leafpad", root=root)

    assert result is win, f"Expected to find window by class, got {result!r}"
    ok("find_by_class matches exact name case-insensitive (Leafpad → leafpad)")


def test_find_by_class_substring():
    """find_by_class matches substring in WM_CLASS."""
    root = mock.MagicMock()
    root.query_tree.return_value.children = []

    win = make_mock_window(
        wm_name="Leafpad",
        wm_class=("leafpad", "Leafpad"),
    )
    root.query_tree.return_value.children = [win]

    mock_xd = mock.MagicMock()
    wf = kp_core.WindowFinder(mock_xd, max_attempts=1, retry_sleep=0)
    result = wf.find_by_class("leaf", root=root)

    assert result is win, f"Expected to find window by substring 'leaf', got {result!r}"
    ok("find_by_class matches substring in class name (Leafpad → leaf)")


def test_find_by_name_substring():
    """find_by_name matches substring in WM_NAME."""
    root = mock.MagicMock()
    root.query_tree.return_value.children = []

    win = make_mock_window(
        wm_name="test.txt - Leafpad",
        wm_class=("leafpad", "Leafpad"),
    )
    root.query_tree.return_value.children = [win]

    mock_xd = mock.MagicMock()
    wf = kp_core.WindowFinder(mock_xd, max_attempts=1, retry_sleep=0)
    result = wf.find_by_name("leafpad", root=root)

    assert result is win, f"Expected to find window by name substring, got {result!r}"
    ok("find_by_name matches substring in window title (test.txt - Leafpad → leafpad)")


def test_find_by_pid_exact():
    """find_by_pid matches _NET_WM_PID exactly."""
    root = mock.MagicMock()
    root.query_tree.return_value.children = []

    win = make_mock_window(wm_name="myapp", wm_class=("myapp", "Myapp"))
    root.query_tree.return_value.children = [win]

    mock_xd = mock.MagicMock()
    wf = kp_core.WindowFinder(mock_xd, max_attempts=1, retry_sleep=0)

    def gfp_side_effect(window, atom_name, *_a, **_kw):
        if window is win and atom_name == '_NET_WM_PID':
            prop = mock.MagicMock()
            prop.value = [1234]
            return prop
        return None

    with mock.patch('kp_core.get_full_property', side_effect=gfp_side_effect):
        result = wf.find_by_pid(1234, root=root)

    assert result is win, f"Expected to find window by PID 1234, got {result!r}"
    ok("find_by_pid matches _NET_WM_PID=1234 exactly")


def test_find_fallback_chain():
    """strategy='all' tries class→role→name and succeeds on name."""
    root = mock.MagicMock()
    root.query_tree.return_value.children = []

    win = make_mock_window(
        wm_name="target app",
        wm_class=("app", "AppClass"),
    )
    root.query_tree.return_value.children = [win]

    mock_xd = mock.MagicMock()
    wf = kp_core.WindowFinder(mock_xd, max_attempts=1, retry_sleep=0)

    # "target" does not appear in any class or role; only in name
    result = wf.find("target", strategy='all', root=root)

    assert result is win, f"Expected fallback to find by name, got {result!r}"
    ok("find with strategy='all' falls back class→role→ to name")


def test_find_none_raises():
    """When all strategies fail, RuntimeError is raised."""
    root = mock.MagicMock()
    root.query_tree.return_value.children = []

    # Empty tree — no window to match
    mock_xd = mock.MagicMock()
    wf = kp_core.WindowFinder(mock_xd, max_attempts=1, retry_sleep=0)

    try:
        wf.find("nonexistent", strategy='all', root=root)
        fail("find_none_raises: RuntimeError was not raised")
    except RuntimeError:
        ok("find raises RuntimeError when no window matches any strategy")


def test_list_windows_filters_unnamed():
    """list_windows skips windows without a name."""
    root = make_mock_window(
        wm_name=None,  # root is skipped
        wm_class=None,
        children=[]
    )

    named = make_mock_window(
        wm_name="Visible App",
        wm_class=("app", "AppClass"),
        window_id=100,
    )
    unnamed = make_mock_window(
        wm_name=None,       # no name
        wm_class=("hidden", "Hidden"),
        window_id=200,
    )
    root.query_tree.return_value.children = [named, unnamed]

    mock_xd = mock.MagicMock()
    wf = kp_core.WindowFinder(mock_xd, max_attempts=1, retry_sleep=0)

    with mock.patch('kp_core.get_full_property', return_value=None):
        result = wf.list_windows(root=root)

    assert len(result) == 1, f"Expected 1 window (named only), got {len(result)}"
    assert result[0]['id'] == 100, f"Expected id 100, got {result[0]['id']}"
    assert result[0]['name'] == "Visible App"
    ok("list_windows skips windows with no WM_NAME")


def test_find_retries():
    """find_by_class retries on failure, sleeping between attempts."""
    root = mock.MagicMock()
    root.query_tree.return_value.children = []   # no windows

    mock_xd = mock.MagicMock()
    wf = kp_core.WindowFinder(mock_xd, max_attempts=3, retry_sleep=0.5)

    with mock.patch('time.sleep') as m_sleep:
        result = wf.find_by_class("anything", root=root)

    assert result is None, "Expected no result from empty tree"
    assert m_sleep.call_count == 3, \
        f"Expected sleep called 3 times, got {m_sleep.call_count}"
    # Check that the sleep interval is the configured retry_sleep
    for call_args in m_sleep.call_args_list:
        assert call_args[0][0] == 0.5, \
            f"Expected sleep(0.5), got sleep({call_args[0][0]!r})"
    ok("_retry_search sleeps max_attempts times with configured delay")


test_find_by_class_exact()
test_find_by_class_substring()
test_find_by_name_substring()
test_find_by_pid_exact()
test_find_fallback_chain()
test_find_none_raises()
test_list_windows_filters_unnamed()
test_find_retries()

# ---------------------------------------------------------------------------
# WindowController tests
# ---------------------------------------------------------------------------

print("\n=== WindowController tests ===")


def test_is_valid_true():
    wc = kp_core.WindowController(mock.MagicMock())
    win = mock.MagicMock()
    # get_attributes() succeeds (default MagicMock behavior — no exception)
    assert wc.is_valid(win) is True
    ok("is_valid returns True when get_attributes() succeeds")


def test_is_valid_false():
    wc = kp_core.WindowController(mock.MagicMock())
    win = mock.MagicMock()
    win.get_attributes.side_effect = Exception("BadWindow")
    assert wc.is_valid(win) is False
    ok("is_valid returns False when get_attributes() raises")


def test_focus_calls_set_input_focus():
    xd = mock.MagicMock()
    xd.root.return_value = mock.MagicMock()
    xd.display.intern_atom.return_value = mock.MagicMock()

    # Set up _verify_focus to pass on first attempt
    focus_result = mock.MagicMock()
    focus_result.focus = None  # placeholder, we set this after creating win

    wc = kp_core.WindowController(xd)
    win = mock.MagicMock()

    focus_result.focus = win
    xd.display.get_input_focus.return_value = focus_result

    result = wc.focus(win, max_retries=1)
    assert result is True, f"Expected focus to return True, got {result}"
    win.set_input_focus.assert_called_with(
        kp_core.X.RevertToParent, kp_core.X.CurrentTime,
    )
    win.configure.assert_called_with(stack_mode=kp_core.X.Above)
    ok("focus calls set_input_focus and returns True on success")


def test_focus_returns_false_for_invalid():
    xd = mock.MagicMock()
    xd.root.return_value = mock.MagicMock()
    xd.display.intern_atom.return_value = mock.MagicMock()

    wc = kp_core.WindowController(xd)
    win = mock.MagicMock()
    # Every X operation raises — focus cannot succeed
    win.set_input_focus.side_effect = Exception("BadWindow")

    result = wc.focus(win, max_retries=1)
    assert result is False, f"Expected focus to return False, got {result}"
    ok("focus returns False when window operations fail")


test_is_valid_true()
test_is_valid_false()
test_focus_calls_set_input_focus()
test_focus_returns_false_for_invalid()

# ---------------------------------------------------------------------------
# ProgramLauncher tests
# ---------------------------------------------------------------------------

print("\n=== ProgramLauncher tests ===")


@mock.patch('subprocess.Popen')
def test_launch_no_shell_true(mock_popen):
    mock_proc = mock.MagicMock()
    mock_proc.pid = 99999
    mock_popen.return_value = mock_proc

    pl = kp_core.ProgramLauncher()
    pid = pl.launch("echo hello")

    assert pid == 99999, f"Expected PID 99999, got {pid}"
    mock_popen.assert_called_once()
    # shell is not passed explicitly → defaults to False
    call_kwargs = mock_popen.call_args[1]
    assert 'shell' not in call_kwargs, \
        f"shell should not be passed, got kwargs: {call_kwargs}"
    ok("launch calls subprocess.Popen without shell=True")


@mock.patch('subprocess.Popen')
def test_launch_shlex_split(mock_popen):
    mock_proc = mock.MagicMock()
    mock_proc.pid = 11111
    mock_popen.return_value = mock_proc

    pl = kp_core.ProgramLauncher()
    pl.launch("echo hello   world")

    call_args = mock_popen.call_args[0][0]  # first positional → args list
    assert call_args == ["echo", "hello", "world"], \
        f"Expected shlex-split args, got {call_args!r}"
    ok("launch splits command string via shlex into args list")


@mock.patch('os.killpg')
def test_cleanup_sends_sigterm(mock_killpg):
    pl = kp_core.ProgramLauncher()
    pl.pid = 12345
    pl.process = mock.MagicMock()
    pl.process.wait.return_value = None  # wait succeeds immediately

    pl.cleanup()

    mock_killpg.assert_called_once()
    sig_sent = mock_killpg.call_args[0][1]
    assert sig_sent == signal.SIGTERM, \
        f"Expected SIGTERM ({signal.SIGTERM}), got {sig_sent}"
    ok("cleanup sends SIGTERM via os.killpg")


@mock.patch('os.killpg')
def test_cleanup_fallback_to_sigkill(mock_killpg):
    pl = kp_core.ProgramLauncher()
    pl.pid = 12345
    pl.process = mock.MagicMock()
    # First wait() times out, second succeeds after SIGKILL
    pl.process.wait.side_effect = [
        subprocess.TimeoutExpired("cmd", 3),
        None,
    ]

    pl.cleanup()

    assert mock_killpg.call_count == 2, \
        f"Expected 2 killpg calls, got {mock_killpg.call_count}"
    assert mock_killpg.call_args_list[0][0][1] == signal.SIGTERM, \
        "First killpg should be SIGTERM"
    assert mock_killpg.call_args_list[1][0][1] == signal.SIGKILL, \
        "Second killpg should be SIGKILL"
    ok("cleanup sends SIGKILL after SIGTERM timeout")


@mock.patch('os.killpg')
def test_wait_for_exit_keyboard_interrupt(mock_killpg):
    pl = kp_core.ProgramLauncher()
    pl.pid = 12345
    pl.process = mock.MagicMock()
    pl.process.wait.side_effect = KeyboardInterrupt()

    try:
        pl.wait_for_exit()
        fail("wait_for_exit should have re-raised KeyboardInterrupt")
    except KeyboardInterrupt:
        pass  # expected

    # cleanup() should have been triggered, sending SIGTERM
    mock_killpg.assert_called_once()
    assert mock_killpg.call_args[0][1] == signal.SIGTERM, \
        "cleanup should send SIGTERM on KeyboardInterrupt"
    ok("wait_for_exit calls cleanup and re-raises on KeyboardInterrupt")


test_launch_no_shell_true()
test_launch_shlex_split()
test_cleanup_sends_sigterm()
test_cleanup_fallback_to_sigkill()
test_wait_for_exit_keyboard_interrupt()

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print()
print(f"Results: {PASS} passed, {FAIL} failed")
if FAIL:
    sys.exit(1)
else:
    print("All kp_core tests passed! \u2705")
