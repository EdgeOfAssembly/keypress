#!/usr/bin/env python3
"""
Unified script execution engine for keypress.

Extends expand_script_loops() with variables, conditionals, while loops,
and clipboard commands.  All processing is self-contained and requires
only a duck-typed ``automation`` object providing ``type_text``,
``press_key``, ``send_combo``, ``focus``, ``_get_keycode``, and
``finder`` for window-exists conditions.
"""

import re
import subprocess
import sys
import time

# ---------------------------------------------------------------------------
# expand_script_loops  (verbatim copy from keypress.py)
# ---------------------------------------------------------------------------

def expand_script_loops(lines, _depth=0):
    """Expand <for:N> ... </for> loop blocks in a list of script lines.

    Returns a new flat list of lines with all loops expanded in-place.
    Nested loops are supported.  Raises SystemExit on any malformed syntax:
      - non-integer or out-of-range N in <for:N>
      - a <for:N> block without a matching </for>
      - a stray </for> with no matching <for:N>
    """
    result = []
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        low = stripped.lower()

        # Detect <for:N> opener
        if low.startswith('<for:') and low.endswith('>'):
            inner = stripped[5:-1]  # text between '<for:' and '>'
            try:
                count = int(inner)
            except ValueError:
                print(f"ERROR: Invalid loop count '{inner}' in '{stripped}' (must be an integer >= 1)")
                sys.exit(1)
            if count < 1:
                print(f"ERROR: Loop count must be >= 1, got {count} in '{stripped}'")
                sys.exit(1)

            # Collect body lines up to matching </for>, respecting nesting
            depth = 1
            j = i + 1
            body = []
            while j < len(lines):
                inner_low = lines[j].strip().lower()
                if inner_low.startswith('<for:') and inner_low.endswith('>'):
                    depth += 1
                elif inner_low == '</for>':
                    depth -= 1
                    if depth == 0:
                        break
                body.append(lines[j])
                j += 1
            else:
                # Exhausted lines without finding closing </for>
                print(f"ERROR: Missing </for> for <for:{count}> (opened at script line {i + 1})")
                sys.exit(1)

            # Recursively expand any nested loops in the body, then repeat
            expanded_body = expand_script_loops(body, _depth + 1)
            for _ in range(count):
                result.extend(expanded_body)

            i = j + 1  # resume after the </for>

        # Detect stray </for> with no matching opener
        elif low == '</for>':
            print(f"ERROR: Unexpected </for> at script line {i + 1} with no matching <for:N>")
            sys.exit(1)

        else:
            result.append(lines[i])
            i += 1

    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _find_matching_end(lines, start_idx, open_prefix, close_tag):
    """Return the index of *close_tag* that matches the open tag at *start_idx*.

    Respects nesting so that ``<if:...><if:...></if></if>`` resolves
    correctly.  Returns ``None`` when no matching close tag is found.
    """
    depth = 1
    j = start_idx + 1
    while j < len(lines):
        low = lines[j].strip().lower()
        if low.startswith(open_prefix) and low.endswith('>'):
            depth += 1
        elif low == close_tag:
            depth -= 1
            if depth == 0:
                return j
        j += 1
    return None


def _parse_condition_args(cond):
    """Parse a condition string into ``(func_name, args_list)``.

    Supported forms::

        var_defined("NAME")       -> ('var_defined', ['NAME'])
        eq("NAME","value")        -> ('eq', ['NAME', 'value'])
        ne("NAME","value")        -> ('ne', ['NAME', 'value'])
        window_exists("pattern")  -> ('window_exists', ['pattern'])
        clipboard_empty           -> ('clipboard_empty', [])
        true                      -> ('true', [])
        false                     -> ('false', [])

    Raises :class:`ValueError` for unrecognised condition syntax.
    """
    cond = cond.strip()
    if cond == 'true':
        return ('true', [])
    if cond == 'false':
        return ('false', [])
    if cond == 'clipboard_empty':
        return ('clipboard_empty', [])

    m = re.match(r'(\w+)\((.*)\)', cond)
    if not m:
        raise ValueError(f"Unknown condition syntax: {cond!r}")
    func = m.group(1)
    args_str = m.group(2)
    args = re.findall(r'"([^"]*)"', args_str)
    return (func, args)


def _is_clipboard_empty():
    """Return True when the X11 clipboard appears empty (tested via xclip / xsel)."""
    for cmd in (
        ['xclip', '-selection', 'clipboard', '-o'],
        ['xsel', '--clipboard', '--output'],
    ):
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                return False
        except Exception:
            continue
    return True


def _find_else_block(lines, if_start, end_idx):
    """Locate a top-level ``<else>`` line within an ``<if>`` block.

    Returns the line index of ``<else>``, or ``None`` when no top-level
    else block exists.  Skips ``<else>`` lines nested inside sub-``<if:>``
    blocks.
    """
    depth = 0
    for j in range(if_start, end_idx):
        low = lines[j].strip().lower()
        if low.startswith('<if:') and low.endswith('>'):
            depth += 1
        elif low == '</if>':
            if depth > 0:
                depth -= 1
        elif low == '<else>' and depth == 0:
            return j
    return None


# ---------------------------------------------------------------------------
# expand_variables
# ---------------------------------------------------------------------------

def expand_variables(line, vars_dict):
    """Replace ``${VAR}`` and ``${VAR:-default}`` placeholders in *line*.

    Parameters
    ----------
    line : str
        The raw line that may contain variable references.
    vars_dict : dict or None
        Mapping of variable names to their string values.  If *None* or
        empty the function returns *line* unchanged (except for defaults).

    Supported syntax
    ----------------
    ``${VAR}``
        Replaced with the value of *VAR* from *vars_dict*.  If *VAR* is
        absent the literal ``${VAR}`` is kept.
    ``${VAR:-default}``
        Replaced with the value of *VAR*; falls back to ``default`` when
        *VAR* is absent or *vars_dict* is None.
    ``$$``
        Escaped to a single literal ``$``.
    """
    if not vars_dict:
        vars_dict = {}

    def _replace(match):
        text = match.group(1)
        if ':-' in text:
            name, default = text.split(':-', 1)
            return vars_dict.get(name, default)
        return vars_dict.get(text, match.group(0))

    line = line.replace('$$', '\x00DOLLAR\x00')
    line = re.sub(r'\$\{(.+?)\}', _replace, line)
    line = line.replace('\x00DOLLAR\x00', '$')
    return line


# ---------------------------------------------------------------------------
# evaluate_condition
# ---------------------------------------------------------------------------

def evaluate_condition(condition_str, automation, vars_dict):
    """Evaluate a boolean condition expression.

    Parameters
    ----------
    condition_str : str
        A condition expression (e.g. ``"eq(\\"MODE\\",\\"debug\\")"``).
        May be prefixed with ``not:`` to negate the result.
    automation
        An object providing ``finder.find_by_name()`` (needed for
        ``window_exists`` checks).  May be ``None`` when testing
        conditions that do not require the automation object.
    vars_dict : dict or None
        Variable store used by ``var_defined``, ``eq``, and ``ne``.

    Supported conditions
    --------------------
    ``var_defined("NAME")``
        Returns True when *NAME* is a key in *vars_dict*.
    ``eq("NAME", "value")``
        Returns True when ``vars_dict[NAME] == value``.
    ``ne("NAME", "value")``
        Returns True when ``vars_dict[NAME] != value``.
    ``window_exists("pattern")``
        Returns True when ``automation.finder.find_by_name(pattern)``
        returns a non-None window.
    ``clipboard_empty``
        True when the X11 clipboard yields no content (tested via xclip
        or xsel).
    ``true`` / ``false``
        Literal boolean values.
    ``not:...``
        Negates the sub-condition that follows the colon.

    Returns
    -------
    bool
    """
    negate = False
    if condition_str.startswith('not:'):
        negate = True
        condition_str = condition_str[4:]

    func, args = _parse_condition_args(condition_str)

    if func == 'var_defined':
        result = (vars_dict is not None and args[0] in vars_dict)
    elif func == 'eq':
        if vars_dict is None:
            result = False
        else:
            result = (vars_dict.get(args[0]) == args[1])
    elif func == 'ne':
        if vars_dict is None:
            result = (args[1] != '')
        else:
            result = (vars_dict.get(args[0]) != args[1])
    elif func == 'window_exists':
        if automation is None or not hasattr(automation, 'finder'):
            result = False
        else:
            result = (automation.finder.find_by_name(args[0]) is not None)
    elif func == 'clipboard_empty':
        result = _is_clipboard_empty()
    elif func == 'true':
        result = True
    elif func == 'false':
        result = False
    else:
        print(f"Warning: Unknown condition function '{func}'")
        result = False

    return not result if negate else result


# ---------------------------------------------------------------------------
# execute_script
# ---------------------------------------------------------------------------

def execute_script(lines, automation, vars_dict=None, timeout=0):
    """Execute a list of script lines with variables, conditionals, and loops.

    Parameters
    ----------
    lines : list[str]
        Script lines (typically with trailing ``\\n`` from :func:`readlines`).
        ``<for:N> ... </for>`` blocks are expanded before the per-line
        dispatch.
    automation
        Duck-typed object providing at least::

            type_text(text)          # type a string
            press_key(keycode, mod)  # press+release a key
            send_combo(combo_str)    # e.g. "Ctrl+Alt+Del"
            focus()                  # bring window to front
            _get_keycode(key_name)   # -> (keycode, modifier) or (None, 0)
            SPECIAL_KEYS             # dict mapping names to keycodes
            finder.find_by_name(p)   # for window-exists checks (optional)

    vars_dict : dict or None
        Variable name -> value mapping.  Expanded via
        :func:`expand_variables` on every line (including conditions).
    timeout : float
        Global timeout in seconds.  Currently reserved; per-while timeouts
        use the ``<while:timeout:N:condition>`` syntax.

    Returns
    -------
    None
    """

    lines = expand_script_loops(lines)
    if vars_dict is None:
        vars_dict = {}

    ret_keycode = getattr(automation, 'SPECIAL_KEYS', {}).get('return', 36)
    global_start = time.time()
    i = 0

    while_stack = []   # list of dicts: {body_start, end, timeout, start_time, condition_str}

    while i < len(lines):
        if timeout > 0 and (time.time() - global_start) > timeout:
            print("[timeout] Global timeout reached.")
            break

        raw_line = lines[i]
        line = raw_line.rstrip('\n')
        line = expand_variables(line, vars_dict)

        # Skip blank lines and comments
        if not line or line.lstrip().startswith('#'):
            i += 1
            continue

        stripped = line.strip()
        low = stripped.lower()

        # ---- Block tags --------------------------------------------------
        if low.startswith('<if:') and low.endswith('>'):
            end_idx = _find_matching_end(lines, i, '<if:', '</if>')
            if end_idx is None:
                print(f"ERROR: Missing </if> for if-block at line {i + 1}")
                sys.exit(1)

            condition_str = expand_variables(
                stripped[4:-1].strip(),  # content between <if: and >
                vars_dict,
            )
            try:
                cond = evaluate_condition(condition_str, automation, vars_dict)
            except ValueError as e:
                print(f"ERROR: Invalid condition at line {i + 1}: {e}")
                sys.exit(1)
            print(f"  [if: {condition_str}] -> {cond}")

            else_idx = _find_else_block(lines, i + 1, end_idx)
            if else_idx is not None:
                if_body = lines[i + 1:else_idx]
                else_body = lines[else_idx + 1:end_idx]
            else:
                if_body = lines[i + 1:end_idx]
                else_body = []

            active_body = if_body if cond else else_body
            if active_body:
                # Process the body inline
                sub_i = 0
                while sub_i < len(active_body):
                    sub_raw = active_body[sub_i]
                    sub_line = expand_variables(sub_raw.rstrip('\n'), vars_dict)
                    sub_stripped = sub_line.strip()
                    sub_low = sub_stripped.lower()

                    if not sub_line or sub_line.lstrip().startswith('#'):
                        sub_i += 1
                        continue

                    if sub_low.startswith('<if:') and sub_low.endswith('>'):
                        # Recursive if – not in this flat dispatch; bodies
                        # nested inside if/else are plain lines (no block
                        # commands inside the body of an inner if handled
                        # here, but we support it by re-calling
                        # execute_script-style logic).
                        # For simplicity we rely on the fact that expanded
                        # loops are flat; inner if-blocks within bodies are
                        # executed via a recursive call to _execute_block.
                        _execute_block(
                            sub_raw, active_body, sub_i, len(active_body),
                            automation, vars_dict,
                        )
                        # _execute_block processes the block and returns
                        # the new sub_i.
                        sub_i = _execute_block(
                            sub_raw, active_body, sub_i, len(active_body),
                            automation, vars_dict,
                        )
                        continue

                    _dispatch_line(sub_stripped, sub_low, automation, vars_dict, vars_dict)
                    sub_i += 1

            i = end_idx + 1
            continue

        if low.startswith('<while:') and low.endswith('>'):
            inner = stripped[7:-1]  # text between '<while:' and '>'

            # Parse optional timeout prefix
            parsed_timeout = 0.0
            condition_str = inner
            if inner.startswith('timeout:'):
                rest = inner[8:]
                colon_idx = rest.find(':')
                if colon_idx == -1:
                    print(f"ERROR: Invalid while timeout syntax at line {i + 1}: '{inner}'")
                    sys.exit(1)
                try:
                    parsed_timeout = float(rest[:colon_idx])
                except ValueError:
                    print(f"ERROR: Invalid timeout value at line {i + 1}: '{rest[:colon_idx]}'")
                    sys.exit(1)
                condition_str = rest[colon_idx + 1:]

            condition_str = expand_variables(condition_str, vars_dict)

            end_idx = _find_matching_end(lines, i, '<while:', '</while>')
            if end_idx is None:
                print(f"ERROR: Missing </while> for while-block at line {i + 1}")
                sys.exit(1)

            try:
                cond = evaluate_condition(condition_str, automation, vars_dict)
            except ValueError as e:
                print(f"ERROR: Invalid condition at line {i + 1}: {e}")
                sys.exit(1)
            print(f"  [while: {condition_str}] -> {cond}")

            if not cond:
                i = end_idx + 1
                continue

            ctx = {
                'body_start': i + 1,
                'end': end_idx,
                'timeout': parsed_timeout,
                'start_time': time.time(),
                'condition_str': condition_str,
            }
            while_stack.append(ctx)
            i = i + 1
            continue

        if low == '<break>':
            if not while_stack:
                print(f"ERROR: <break> at line {i + 1} outside of while loop")
                sys.exit(1)
            ctx = while_stack.pop()
            print(f"  [break]")
            i = ctx['end'] + 1
            continue

        # ---- Dispatch single-line commands --------------------------------
        _dispatch_line(stripped, low, automation, vars_dict, vars_dict)

        # ---- Enter handling for text lines --------------------------------
        # Text lines end with Enter unless the *next* line is <nowait>.
        if not (low.startswith('<') and low.endswith('>')):
            if i + 1 < len(lines) and lines[i + 1].strip().lower() == '<nowait>':
                i += 2   # skip nowait line too
            else:
                automation.focus()
                automation.press_key(ret_keycode, 0)
                i += 1
        else:
            if low == '<nowait>':
                # <nowait> appearing standalone (no preceding text) is just consumed.
                i += 1
            else:
                i += 1

        # ---- While-loop re-evaluation after advancing i --------------------
        while while_stack and i >= while_stack[-1]['end']:
            ctx = while_stack[-1]
            timeout_ok = True
            if ctx['timeout'] > 0:
                elapsed = time.time() - ctx['start_time']
                if elapsed >= ctx['timeout']:
                    timeout_ok = False
                    print(f"  [while timeout: {ctx['timeout']}s]")

            if timeout_ok:
                try:
                    cond = evaluate_condition(
                        expand_variables(ctx['condition_str'], vars_dict),
                        automation, vars_dict,
                    )
                except ValueError:
                    cond = False
                print(f"  [while: {ctx['condition_str']}] -> {cond}")
                if cond:
                    i = ctx['body_start']  # loop back
                    break
            while_stack.pop()
            i = ctx['end'] + 1


def _execute_block(opener_line, lines, start_i, limit_i, automation, vars_dict):
    """Process an ``<if:...>`` block found inside an if/else body.

    Returns the new index (one past the block's ``</if>``).
    """
    end_idx = _find_matching_end(lines, start_i, '<if:', '</if>')
    if end_idx is None:
        print(f"WARNING: Missing </if> in nested block")
        return start_i + 1

    stripped = opener_line.rstrip('\n').strip()
    condition_str = expand_variables(stripped[4:-1].strip(), vars_dict)
    try:
        cond = evaluate_condition(condition_str, automation, vars_dict)
    except ValueError:
        cond = False
    print(f"  [if: {condition_str}] -> {cond}")

    else_idx = _find_else_block(lines, start_i + 1, end_idx)
    if else_idx is not None:
        active_body = lines[start_i + 1:else_idx] if cond else lines[else_idx + 1:end_idx]
    else:
        active_body = lines[start_i + 1:end_idx] if cond else []

    sub_i = 0
    while sub_i < len(active_body):
        sub_raw = active_body[sub_i]
        sub_line = expand_variables(sub_raw.rstrip('\n'), vars_dict)
        sub_stripped = sub_line.strip()
        sub_low = sub_stripped.lower()

        if not sub_line or sub_line.lstrip().startswith('#'):
            sub_i += 1
            continue

        _dispatch_line(sub_stripped, sub_low, automation, vars_dict, vars_dict)
        sub_i += 1

    return end_idx + 1


def _dispatch_line(stripped, low, automation, vars_dict, default_vars):
    """Execute a single command or text line.

    *stripped* and *low* are the already-expanded and stripped versions
    of the line (for efficiency, avoid re-stripping inside the dispatch).
    """
    if low == '<nowait>':
        return

    if low == '<clipboard:get>':
        print("  [clipboard: get]")
        _handle_clipboard_get(automation)
        return

    if low.startswith('<clipboard:set:'):
        text = stripped.split(':set:', 1)[1].lstrip('>')
        print("  [clipboard: set]")
        _handle_clipboard_set(text)
        return

    if low.startswith('<wait:'):
        try:
            seconds = float(stripped.split(':', 1)[1].rstrip('>'))
        except ValueError:
            print(f"Warning: Invalid wait command '{stripped}'")
            return
        print(f"  [waiting {seconds}s]")
        time.sleep(seconds)
        return

    if low.startswith('<'):
        inner = stripped[1:-1].strip()
        inner_low = inner.lower()

        if '+' in inner:
            print(f"  [combo: {inner}]")
            automation.send_combo(inner)
            return

        keycode, modifier = automation._get_keycode(inner)
        if keycode:
            print(f"  [key: {inner}]")
            automation.focus()
            automation.press_key(keycode, modifier)
        else:
            print(f"Warning: Unknown key '{inner}'")
        return

    # Regular text
    print(f"  > {stripped}")
    automation.type_text(stripped)


def _handle_clipboard_get(automation):
    """Read clipboard via xclip and type the result."""
    try:
        result = subprocess.run(
            ['xclip', '-selection', 'clipboard', '-o'],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout:
            automation.type_text(result.stdout)
    except Exception:
        try:
            result = subprocess.run(
                ['xsel', '--clipboard', '--output'],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout:
                automation.type_text(result.stdout)
        except Exception:
            pass


def _handle_clipboard_set(text):
    """Set clipboard content via xclip (fallback: xsel)."""
    try:
        subprocess.run(
            ['xclip', '-selection', 'clipboard'],
            input=text.encode(), check=True, timeout=5,
        )
    except Exception:
        try:
            subprocess.run(
                ['xsel', '--clipboard', '--input'],
                input=text.encode(), check=True, timeout=5,
            )
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Demo / smoketest  (no X11 required)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import unittest.mock as mock

    print("=== expand_script_loops ===")
    test_lines = [
        "<for:3>\n", "hello\n", "</for>\n",
    ]
    result = expand_script_loops(test_lines)
    print("  Input :", [l.rstrip() for l in test_lines])
    print("  Output:", [l.rstrip() for l in result])
    assert len(result) == 3
    print("  OK")

    test_nested = ["<for:2>\n", "<for:3>\n", "x\n", "</for>\n", "</for>\n"]
    nested_result = expand_script_loops(test_nested)
    assert len(nested_result) == 6
    print("  Nested expand OK (6 lines)")

    print("\n=== expand_variables ===")
    vd = {"USER": "admin", "MODE": "debug"}
    assert expand_variables("Hello ${USER}", vd) == "Hello admin"
    assert expand_variables("${MODE}", vd) == "debug"
    assert expand_variables("${UNKNOWN:-guest}", vd) == "guest"
    assert expand_variables("${UNKNOWN}", vd) == "${UNKNOWN}"
    assert expand_variables("$$${USER}", vd) == "$admin"
    assert expand_variables("Cost: $$5", vd) == "Cost: $5"
    assert expand_variables("No vars", vd) == "No vars"
    assert expand_variables("No vars", None) == "No vars"
    print("  All variable tests passed")

    print("\n=== evaluate_condition ===")
    from script_engine import evaluate_condition

    assert evaluate_condition("true", None, {}) is True
    assert evaluate_condition("false", None, {}) is False
    assert evaluate_condition("not:true", None, {}) is False
    assert evaluate_condition("not:false", None, {}) is True
    assert evaluate_condition('var_defined("USER")', None, {"USER": "x"}) is True
    assert evaluate_condition('var_defined("MISSING")', None, {"USER": "x"}) is False
    assert evaluate_condition('eq("USER","x")', None, {"USER": "x"}) is True
    assert evaluate_condition('eq("USER","y")', None, {"USER": "x"}) is False
    assert evaluate_condition('ne("USER","y")', None, {"USER": "x"}) is True
    assert evaluate_condition('not:eq("USER","x")', None, {"USER": "x"}) is False
    print("  All condition tests passed")

    print("\n=== execute_script smoketest ===")
    auto = mock.MagicMock()
    auto.focus.return_value = True
    auto._get_keycode.return_value = (36, 0)
    auto.SPECIAL_KEYS = {'return': 36}
    auto.finder = mock.MagicMock()

    script = [
        "# comment\n",
        "Hello ${NAME}\n",
        "<if:eq(\"NAME\",\"admin\")>\n",
        "admin mode\n",
        "</if>\n",
    ]
    execute_script(script, auto, {"NAME": "admin"})
    calls = [c.args[0] for c in auto.type_text.call_args_list]
    assert calls == ["Hello admin", "admin mode"], f"got {calls}"
    print(f"  Typed: {calls}")
    print("  If-block OK")

    auto.reset_mock()
    auto.focus.return_value = True
    auto._get_keycode.return_value = (36, 0)
    auto.SPECIAL_KEYS = {'return': 36}

    script2 = [
        "<for:2>\n",
        "<key>\n",
        "</for>\n",
    ]
    execute_script(script2, auto, {})
    assert auto.type_text.call_count == 0
    assert auto.press_key.call_count == 2
    print("  For+key dispatch OK")

    print("\nAll smoke tests passed!")
