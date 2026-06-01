# Feature 01: `--list-windows` Flag

## Status
**READY TO IMPLEMENT — standalone, already proven safe**

## What It Does
Adds a `--list-windows` CLI flag. When present, the script queries the X11 root window tree, prints all visible windows in format `0x{hexid} | {WM_NAME}`, and exits with code 0. No program is launched, no focus is attempted.

## Why It's Safe
- Only touches `main()` (the argparse setup and early-exit path)
- Zero changes to `KeypressAutomation` class or X11 engine methods
- Does not require launching a program, so no PID/window lifecycle issues

## Implementation Steps

1. Change `parser.add_argument('program', ...)` to `parser.add_argument('program', nargs='?', ...)` so program is optional.
2. Add `parser.add_argument('--list-windows', action='store_true', ...)`.
3. After `args = parser.parse_args()`, add early-exit block:
   ```python
   if args.list_windows:
       d = display.Display()
       root = d.screen().root
       tree = root.query_tree()
       print("Visible windows (hex id | name):")
       for w in tree.children:
           try:
               name = w.get_wm_name()
               if name:
                   print(f"0x{w.id:08x} | {name}")
           except Exception:
               pass
       return 0
   ```
4. Wrap existing validation in `if not args.list_windows:` guard.

## Test Plan

| Step | Command | Expected |
|------|---------|---------|
| 1 | `./keypress.py --list-windows \| head` | Lists windows, shows at least one entry |
| 2 | `./keypress.py --list-windows \| grep -i leafpad` | Shows Leafpad entry |
| 3 | `python3 test_loops.py && python3 test_integration.py` | 15 + 11 pass (zero failures) |
| 4 | `./keypress.py "leafpad" -c "test" -w leafpad -n` | Still types normally (regression test) |

## Estimated Diff Size
~25 lines in `main()` only.

## Reference
Already implemented in an earlier session. See git history if needed, but re-implementing from these instructions is safer than copying the old diff ( avoids drift from current keypress.py).
