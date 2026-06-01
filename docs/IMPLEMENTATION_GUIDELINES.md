# Implementation Guidelines for keypress.py Future Features

## The Golden Rule

**`keypress.py` contains battle-tested X11 code. Treat `focus()`, `type_text()`, `press_key()`, `_build_keymap_cache()`, and `_keysym_to_char()` as sacred. Do NOT rewrite them. Do NOT replace them with imports from `kp_core.py` or `script_engine.py`. ONLY add small, safe, well-tested blocks of new logic AROUND the existing proven code.**

## Before Starting Any Feature

1. Create a Git branch: `git checkout -b feature/<name>`
2. Write the doc for this feature FIRST (`docs/FEATURE_XX_name.md`)
3. Implement exactly per the doc, nothing extra
4. Run the full test suite: `python3 test_loops.py && python3 test_integration.py`
5. Test on the REAL DISPLAY (Finnish layout, `DISPLAY=:0`, leafpad)
6. Only when ALL tests pass AND real display works, consider the feature complete
7. PR, review, merge. Then move to the NEXT feature on the next branch.

## Testing Order (Mandatory)

Every feature MUST pass these in order before being considered complete:

1. **Unit tests**: `python3 test_loops.py` (15 tests) + `python3 test_integration.py` (11 tests)
2. **Real display test**: Attach to leafpad on `DISPLAY=:0` and type at least one ASCII string.
3. **If the feature involves typing**: Type international characters (`café`, `naïve`) to verify compose fallback or keymap correctness.
4. **Edge cases**: Test with `--emulator-mode`, test without `-w` (PID search), test with empty script.

## What Is Forbidden

- Replacing existing `focus()`, `type_text()`, or `press_key()` with calls to `kp_core.WindowController`
- Adding extra `focus()` calls before every keypress (the existing code calls it once before a batch)
- Using `EWMH _NET_ACTIVE_WINDOW` — the original code uses `X.RevertToParent` which works on LxDE. `BadMatch` errors are harmless and expected.
- Modifying `_check_window_valid()` behavior
- Removing `time.sleep()` calls inside `press_key()` or `type_text()` — they are load-bearing for X11 event ordering
- Adding `self.display.sync()` after every single key event — the original only syncs at strategic points
- Using `--attach` to test compose fallback — launch a new leafpad (`--attach` tests different codepaths and may mask bugs)

## File Size Warning

The original working `keypress.py` is **787 lines**. If your feature additions are pushing it past 900 lines, you're doing too much at once. Split into multiple features.

## Diff Check Before Commit

Run `git diff keypress.py` and verify:

- Lines 1-430 are unchanged (or only have new constant additions near the class top)
- Lines 431-510 (`focus()`, `press_key()`, `_get_keycode_*()`) are COMPLETELY unchanged
- Lines 620-660 (`type_text()`) may have a SMALL conditional block added but no structural changes
- Lines 705-788 (`main()`) may have new argparse entries and validation logic

If the diff touches more than 50 lines inside the core engine, stop and reconsider.

## Commit Message Format

```
Feature: <short name>

- What changed
- Test results: X unit tests + Y integration tests pass
- Real display verified: yes/no
```

## If Things Break

1. **STOP** immediately. Do not pile on more fixes.
2. `git checkout 322ece1 -- keypress.py` (the known-good original)
3. Document the failure in `docs/LESSONS_LEARNED.md`
4. Start over with a smaller scope.
