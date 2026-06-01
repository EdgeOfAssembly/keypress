# Lessons Learned: What We Got Wrong and How to Avoid It

## Overview

We attempted to add four features to `keypress.py` (`--list-windows`, `--attach`, compose fallback, and variable substitution) in what was supposed to be "iterative, safe additions." The result: hundreds of lines of changes, broken real-display behavior, and a complete rollback. This document is the honest autopsy.

## Lesson 1: "One Feature Per Branch" Means ONE FEATURE, Per Branch, Per Session

### What We Did Wrong
We used a `deep-coder` subagent with a single massive prompt asking for 3 features at once (`--attach`, compose fallback, and variable substitution). The subagent made **143 changes across 152 lines** in a single shot. We could not easily test which feature broke what.

### What To Do Instead
Create ONE branch, implement ONE feature, run ALL tests, verify on real display, merge it, THEN create the next branch. Do NOT batch features.

### The Rule
If your diff touches `keypress.py` in more than one conceptual area (e.g., both `type_text()` internals AND `main()` CLI parsing), you are doing too much.

## Lesson 2: "Tests Pass" on Xvfb Does NOT Mean "Works on Real Display"

### What We Did Wrong
The subagent reported "all tests pass" for the compose fallback feature. But those tests run with MOCKED Xlib (via `sys.modules` injection). They do not exercise:
- Actual `set_input_focus()` X11 calls
- Actual keyboard layout keycode scanning
- Actual Finnish dead keys at real keycodes

When we tested on the real display, the compose fallback produced `caf'e na"ive` instead of `café naïve` because dead keys were being pressed with WRONG modifiers (due to a variable leak in `_build_keymap_cache()` that the Xvfb tests couldn't catch).

### What To Do Instead
Every feature that involves typing MUST be tested on a real display with a real Finnish keyboard layout. Xvfb tests are necessary but NOT sufficient.

**MANDATORY real-display test script for any typing-related feature:**
```bash
# 1. Verify it still works with normal ASCII
DISPLAY=:0 ./keypress.py "leafpad" -c "ASCII test" -w leafpad -n
# Should show: ASCII test

# 2. Verify compose fallback if applicable
DISPLAY=:0 ./keypress.py --attach-window-id 0x03000037 -c "café naïve" -n
# Should show: café naïve  (NOT caf'e na"ive)
# If this is wrong, STOP. Do not proceed.

# 3. All legacy tests must still pass
python3 test_loops.py && python3 test_integration.py
```

## Lesson 3: The `modifier` Variable Leak Was a Dumb Bug That Should Never Have Happened

### What We Did Wrong
In `_build_keymap_cache()`, we added code to cache dead keys:
```python
if char:  # normal character
    modifier = calculate_modifier(col)  # modifier SET here
    self.keymap_cache[char] = (keycode, modifier)

# dead key caching AFTER the if block:
dead_name = self.DEAD_KEY_NAMES.get(keysym)
if dead_name and dead_name not in self.dead_key_cache:
    self.dead_key_cache[dead_name] = (keycode, modifier)  # REUSED modifier!
```

The `modifier` variable was ONLY set when `char` was truthy. If a dead key keysym appeared on a keycode where the previous keycode iteration also had a character but no new `char` was found in the current column, `modifier` retained the WRONG value from a previous iteration.

**The fix was trivial**: Move `modifier = calculate_modifier(col)` to happen BEFORE the `if char:` block, so every column gets its own modifier.

### Why It Wasn't Caught
Because it was BUNDLED with 5 other changes and we tested in the wrong order (Xvfb first, real display later). Variable leaks don't show up in mocked tests because mocked tests don't iterate real keycode tables.

## Lesson 4: `compose_cache.py` Mapping Dead Keys to Regular Characters Was Wrong

### What We Did Wrong
`compose_cache.py` originally had this mapping:
```python
"dead_acute": "'",   # WRONG: maps to regular apostrophe
"dead_diaeresis": '"',  # WRONG: maps to regular quote
```

This meant that when `type_text()` asked `_get_keycode("'")`, it got the regular apostrophe keycode, NOT the dead_acute keycode. On Finnish keyboard, the apostrophe key and the dead_acute key are DIFFERENT keycodes (KC 21 has dead_acute as group 0, but the regular apostrophe character might be somewhere else or not present at all).

So pressing apostrophe + e produced `'e`, not `é`.

### What To Do Instead
`compose_cache.py` must preserve dead key names as literal strings (e.g., `'dead_acute'`). `keypress.py` then needs a separate `dead_key_cache` that maps `dead_acute` → `(keycode, modifier)` discovered during actual keyboard layout scanning.

**Do NOT conflate compose file names with keyboard keycodes.** They are separate namespaces that must be joined explicitly.

## Lesson 5: `BadMatch` X11 Errors Are Harmless (And You Will Cause Harm By "Fixing" Them)

### What We Did Wrong
Earlier in the project, we thought `BadMatch` errors from `set_input_focus()` meant the focus call was "broken" and tried to replace it with `kp_core.WindowController` using EWMH `_NET_ACTIVE_WINDOW`. This made things WORSE: EWMH client messages caused MORE `BadMatch` errors and stuck keys.

### The Truth
The original `keypress.py` uses `X.RevertToParent`, which is the correct focus mode for LxDE. The `BadMatch` errors printed to stderr by py-xlib are harmless (the operation still succeeds). The original code has always had these errors and always worked despite them.

**Rule: If `BadMatch` appears but typing still works correctly, DO NOT try to fix it. It is not broken.**

## Lesson 6: `time.sleep()` in `press_key()` Is Load-Bearing

### What We Did Wrong
In one attempt, we removed `time.sleep(0.02)` calls from `press_key()` and `type_text()` thinking they were "unnecessary delays." The result: stuck keys and lost key events.

### The Truth
X11 is asynchronous. Without pauses between key events, Xlib buffers them in the wrong order. A KeyRelease can overtake a KeyPress, causing the application to think a key is being held down permanently.

**Rule: Never remove `time.sleep()` calls inside `press_key()` or `type_text()`. They are load-bearing for X11 event ordering.**

## Lesson 7: Deep-Coder Subagents Are Fast But Don't Understand X11 Context

### What We Did Wrong
We threw a 300-line prompt at a deep-coder subagent asking for 3 features at once. It delivered code that "looked right" — proper Python syntax, reasonable method names, nice docstrings — but it had no awareness that:
- Finnish keyboards have dead keys at different keycodes than English keyboards
- `modifier` variable scoping matters when iterating X11 keycode tables
- Xvfb tests don't catch modifier bugs

### What To Do Instead
Deep-coder is great for structural code generation, but for X11 features:
1. Write the doc/spec YOURSELF (that's why these `.md` files exist)
2. Implement in tiny increments
3. Test on REAL DISPLAY after EVERY change
4. Do NOT ask deep-coder to "do everything at once"

## The Final Checklist (Print This And Tape It To Your Monitor)

Before ANY change to `keypress.py`:

- [ ] Check out a NEW branch
- [ ] Write the feature doc FIRST (`docs/FEATURE_XX_name.md`)
- [ ] Only touch `main()` or add a tiny conditional block — never rewrite `focus()`, `type_text()`, or `press_key()`
- [ ] After writing code, run `git diff keypress.py` and verify the core engine (lines 431-660) is untouched
- [ ] Run `python3 test_loops.py && python3 test_integration.py`
- [ ] Test on REAL DISPLAY with `DISPLAY=:0 ...`
- [ ] If compose is involved, type `café naïve` and verify diacritics are correct
- [ ] If the feature works, commit with message documenting test results
- [ ] If the feature doesn't work, ROLLBACK to `322ece1` and start over with a smaller scope
