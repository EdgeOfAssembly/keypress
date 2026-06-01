#!/usr/bin/env python3
"""Comprehensive tests for the script_engine.py module."""

import sys
import os
import unittest.mock as mock
import time
import subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import script_engine as se

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


# =============================================================================
# expand_script_loops tests
# =============================================================================

def test_for_basic():
    lines = ["<for:3>\n", "hello\n", "</for>\n"]
    result = se.expand_script_loops(lines)
    expected = ["hello\n", "hello\n", "hello\n"]
    if result == expected:
        ok("test_for_basic")
    else:
        fail("test_for_basic", f"expected {expected}, got {result}")


def test_for_nested():
    lines = ["<for:2>\n", "<for:2>\n", "x\n", "</for>\n", "</for>\n"]
    result = se.expand_script_loops(lines)
    expected = ["x\n", "x\n", "x\n", "x\n"]
    if result == expected:
        ok("test_for_nested")
    else:
        fail("test_for_nested", f"expected 4 lines, got {len(result)}: {result}")


def test_for_error_zero():
    lines = ["<for:0>\n", "hello\n", "</for>\n"]
    try:
        se.expand_script_loops(lines)
        fail("test_for_error_zero", "expected SystemExit")
    except SystemExit:
        ok("test_for_error_zero")


def test_plain_text():
    lines = ["hello\n", "world\n"]
    result = se.expand_script_loops(lines)
    expected = ["hello\n", "world\n"]
    if result == expected:
        ok("test_plain_text")
    else:
        fail("test_plain_text", f"expected {expected}, got {result}")


def test_comments_preserved():
    lines = ["# comment\n", "hello\n"]
    result = se.expand_script_loops(lines)
    expected = ["# comment\n", "hello\n"]
    if result == expected:
        ok("test_comments_preserved")
    else:
        fail("test_comments_preserved", f"expected {expected}, got {result}")


# =============================================================================
# expand_variables tests
# =============================================================================

def test_simple():
    result = se.expand_variables("Hello ${USER}", {"USER": "admin"})
    if result == "Hello admin":
        ok("test_simple")
    else:
        fail("test_simple", f"expected 'Hello admin', got '{result}'")


def test_default_used():
    result = se.expand_variables("${FOO:-default}", {})
    if result == "default":
        ok("test_default_used")
    else:
        fail("test_default_used", f"expected 'default', got '{result}'")


def test_default_ignored():
    result = se.expand_variables("${FOO:-default}", {"FOO": "bar"})
    if result == "bar":
        ok("test_default_ignored")
    else:
        fail("test_default_ignored", f"expected 'bar', got '{result}'")


def test_no_vars():
    result = se.expand_variables("plain", {})
    if result == "plain":
        ok("test_no_vars")
    else:
        fail("test_no_vars", f"expected 'plain', got '{result}'")


def test_multiple_vars():
    result = se.expand_variables("${A} ${B}", {"A": "x", "B": "y"})
    if result == "x y":
        ok("test_multiple_vars")
    else:
        fail("test_multiple_vars", f"expected 'x y', got '{result}'")


def test_undefined_warns():
    result = se.expand_variables("${UNDEF}", {})
    if result == "${UNDEF}":
        ok("test_undefined_warns")
    else:
        fail("test_undefined_warns", f"expected '${{UNDEF}}', got '{result}'")


# =============================================================================
# evaluate_condition tests
# =============================================================================

def make_auto():
    auto = mock.MagicMock()
    auto.finder = mock.MagicMock()
    auto.finder.find_by_name.return_value = mock.MagicMock()
    return auto


def test_var_defined_true():
    result = se.evaluate_condition('var_defined("MODE")', None, {"MODE": "x"})
    if result is True:
        ok("test_var_defined_true")
    else:
        fail("test_var_defined_true", f"expected True, got {result}")


def test_var_defined_false():
    result = se.evaluate_condition('var_defined("MODE")', None, {})
    if result is False:
        ok("test_var_defined_false")
    else:
        fail("test_var_defined_false", f"expected False, got {result}")


def test_eq_true():
    result = se.evaluate_condition('eq("MODE","debug")', None, {"MODE": "debug"})
    if result is True:
        ok("test_eq_true")
    else:
        fail("test_eq_true", f"expected True, got {result}")


def test_eq_false():
    result = se.evaluate_condition('eq("MODE","debug")', None, {"MODE": "normal"})
    if result is False:
        ok("test_eq_false")
    else:
        fail("test_eq_false", f"expected False, got {result}")


def test_window_exists():
    auto = make_auto()
    result = se.evaluate_condition('window_exists("leafpad")', auto, {})
    if result is True:
        ok("test_window_exists")
    else:
        fail("test_window_exists", f"expected True, got {result}")


def test_not_negation():
    result = se.evaluate_condition('not:var_defined("X")', None, {})
    if result is True:
        ok("test_not_negation")
    else:
        fail("test_not_negation", f"expected True, got {result}")


def test_true_literal():
    result = se.evaluate_condition('true', None, {})
    if result is True:
        ok("test_true_literal")
    else:
        fail("test_true_literal", f"expected True, got {result}")


def test_clipboard_empty():
    try:
        result = se.evaluate_condition('clipboard_empty', None, {})
        if isinstance(result, bool):
            ok("test_clipboard_empty")
        else:
            fail("test_clipboard_empty", f"expected bool, got {type(result)}")
    except Exception as e:
        fail("test_clipboard_empty", f"exception: {e}")


# =============================================================================
# execute_script tests
# =============================================================================

def make_auto_exec():
    auto = mock.MagicMock()
    auto.type_text = mock.MagicMock()
    auto.press_key = mock.MagicMock()
    auto.send_combo = mock.MagicMock()
    auto.focus = mock.MagicMock(return_value=True)
    auto._get_keycode = mock.MagicMock(return_value=(36, 0))
    auto.SPECIAL_KEYS = {'return': 36}
    auto.finder = mock.MagicMock()
    auto.finder.find_by_name.return_value = None
    return auto


def test_text_lines():
    auto = make_auto_exec()
    lines = ["hello\n", "world\n"]
    se.execute_script(lines, auto, {})
    calls = [c.args[0] for c in auto.type_text.call_args_list]
    press_calls = auto.press_key.call_args_list
    if calls == ["hello", "world"] and len(press_calls) == 2:
        ok("test_text_lines")
    else:
        fail("test_text_lines", f"expected ['hello', 'world'], got {calls}")


def test_if_true():
    auto = make_auto_exec()
    lines = ["<if:true>\n", "hello\n", "</if>\n"]
    se.execute_script(lines, auto, {})
    calls = [c.args[0] for c in auto.type_text.call_args_list]
    if calls == ["hello"]:
        ok("test_if_true")
    else:
        fail("test_if_true", f"expected ['hello'], got {calls}")


def test_if_false():
    auto = make_auto_exec()
    lines = ["<if:false>\n", "hello\n", "</if>\n"]
    se.execute_script(lines, auto, {})
    calls = [c.args[0] for c in auto.type_text.call_args_list]
    if calls == []:
        ok("test_if_false")
    else:
        fail("test_if_false", f"expected [], got {calls}")


def test_if_else_true():
    auto = make_auto_exec()
    lines = ["<if:true>\n", "aaa\n", "<else>\n", "bbb\n", "</if>\n"]
    se.execute_script(lines, auto, {})
    calls = [c.args[0] for c in auto.type_text.call_args_list]
    if calls == ["aaa"]:
        ok("test_if_else_true")
    else:
        fail("test_if_else_true", f"expected ['aaa'], got {calls}")


def test_if_else_false():
    auto = make_auto_exec()
    lines = ["<if:false>\n", "aaa\n", "<else>\n", "bbb\n", "</if>\n"]
    se.execute_script(lines, auto, {})
    calls = [c.args[0] for c in auto.type_text.call_args_list]
    if calls == ["bbb"]:
        ok("test_if_else_false")
    else:
        fail("test_if_else_false", f"expected ['bbb'], got {calls}")


def test_wait():
    auto = make_auto_exec()
    with mock.patch('script_engine.time.sleep') as mock_sleep:
        lines = ["<wait:0.1>\n"]
        se.execute_script(lines, auto, {})
        if mock_sleep.called and mock_sleep.call_args.args[0] == 0.1:
            ok("test_wait")
        else:
            fail("test_wait", f"sleep not called with 0.1")


def test_variables_in_text():
    auto = make_auto_exec()
    lines = ["Hello ${USER}\n"]
    se.execute_script(lines, auto, {"USER": "admin"})
    calls = [c.args[0] for c in auto.type_text.call_args_list]
    if calls == ["Hello admin"]:
        ok("test_variables_in_text")
    else:
        fail("test_variables_in_text", f"expected ['Hello admin'], got {calls}")


def test_clipboard_get():
    auto = make_auto_exec()
    with mock.patch('script_engine.subprocess.run') as mock_run:
        mock_run.return_value = mock.MagicMock(returncode=0, stdout="clipboard_text")
        lines = ["<clipboard:get>\n"]
        se.execute_script(lines, auto, {})
        calls = [c.args[0] for c in auto.type_text.call_args_list]
        if calls == ["clipboard_text"]:
            ok("test_clipboard_get")
        else:
            fail("test_clipboard_get", f"expected ['clipboard_text'], got {calls}")


# =============================================================================
# Nested blocks tests
# =============================================================================

def test_for_inside_if():
    auto = make_auto_exec()
    lines = ["<if:true>\n", "<for:2>\n", "x\n", "</for>\n", "</if>\n"]
    se.execute_script(lines, auto, {})
    calls = [c.args[0] for c in auto.type_text.call_args_list]
    if calls == ["x", "x"]:
        ok("test_for_inside_if")
    else:
        fail("test_for_inside_if", f"expected ['x', 'x'], got {calls}")


def test_if_inside_for():
    auto = make_auto_exec()
    lines = ["<for:2>\n", "<if:true>\n", "x\n", "</if>\n", "</for>\n"]
    se.execute_script(lines, auto, {})
    calls = [c.args[0] for c in auto.type_text.call_args_list]
    if calls == ["x", "x"]:
        ok("test_if_inside_for")
    else:
        fail("test_if_inside_for", f"expected ['x', 'x'], got {calls}")


def test_if_with_variables():
    auto = make_auto_exec()
    lines = ["<if:eq(\"MODE\",\"debug\")>\n", "debug_mode\n", "</if>\n"]
    se.execute_script(lines, auto, {"MODE": "debug"})
    calls = [c.args[0] for c in auto.type_text.call_args_list]
    if calls == ["debug_mode"]:
        ok("test_if_with_variables")
    else:
        fail("test_if_with_variables", f"expected ['debug_mode'], got {calls}")


def test_complex_nested():
    auto = make_auto_exec()
    lines = [
        "<for:2>\n",
        "<if:var_defined(\"X\")>\n",
        "<for:2>\n",
        "${X}\n",
        "</for>\n",
        "</if>\n",
        "</for>\n",
    ]
    se.execute_script(lines, auto, {"X": "value"})
    calls = [c.args[0] for c in auto.type_text.call_args_list]
    if calls == ["value", "value", "value", "value"]:
        ok("test_complex_nested")
    else:
        fail("test_complex_nested", f"expected 4 'value', got {calls}")


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("expand_script_loops")
    print("=" * 60)
    test_for_basic()
    test_for_nested()
    test_for_error_zero()
    test_plain_text()
    test_comments_preserved()

    print("\n" + "=" * 60)
    print("expand_variables")
    print("=" * 60)
    test_simple()
    test_default_used()
    test_default_ignored()
    test_no_vars()
    test_multiple_vars()
    test_undefined_warns()

    print("\n" + "=" * 60)
    print("evaluate_condition")
    print("=" * 60)
    test_var_defined_true()
    test_var_defined_false()
    test_eq_true()
    test_eq_false()
    test_window_exists()
    test_not_negation()
    test_true_literal()
    test_clipboard_empty()

    print("\n" + "=" * 60)
    print("execute_script")
    print("=" * 60)
    test_text_lines()
    test_if_true()
    test_if_false()
    test_if_else_true()
    test_if_else_false()
    test_wait()
    test_variables_in_text()
    test_clipboard_get()

    print("\n" + "=" * 60)
    print("Nested blocks")
    print("=" * 60)
    test_for_inside_if()
    test_if_inside_for()
    test_if_with_variables()
    test_complex_nested()

    print("\n" + "=" * 60)
    print(f"RESULTS: {PASS} passed, {FAIL} failed")
    print("=" * 60)

    sys.exit(1 if FAIL > 0 else 0)
