# Feature 02: `--attach` and `--attach-window-id` Flags

## Status
**READY AFTER Feature 01 is proven — MUST NOT be implemented before `--list-windows` is merged**

## What It Does
Allows `keypress.py` to skip launching a program and instead attach to an already-running window. Two variants:

- `--attach WINDOW_NAME` — Search existing windows for a name match (`_find_window_by_name`), attach to first match.
- `--attach-window-id 0xDEADBEEF` — Create an X11 window object directly from the given hex ID (`display.create_resource_object('window', int(hex, 0))`), skip search entirely.

## Why It Must Wait for Feature 01
Feature 01 introduces the `nargs='?'` change to the `program` arg and the validation guard. Those changes are prerequisites for this feature (because `--attach` usage does not provide a program argument).

## Implementation Steps

1. Add to argparse (after `--list-windows`, before `--debug`):
   ```python
   parser.add_argument('--attach', help='Attach to existing window by name')
   parser.add_argument('--attach-window-id', help='Attach to existing window by hex ID')
   ```
2. Add mutual exclusion / validation in `main()`:
   - If `--attach` XOR `--attach-window-id`, program should be optional.
   - Only `--list-windows` and `--attach*` paths may omit program.
3. Add `attach_to_window()` method to `KeypressAutomation`:
   ```python
   def attach_to_window(self, hex_id=None, name=None):
       if hex_id is not None:
           self.window = self.display.create_resource_object('window', int(hex_id, 0))
           self.window_valid = True
           print(f"Attached to window: {hex_id}")
           return True
       elif name is not None:
           self.window = self._find_window_by_name(name)
           if self.window:
               self.window_valid = True
               print(f"Attached to window: {hex(self.window.id)} - ...")
               return True
           else:
               print(f"WARNING: Could not find window matching '{name}'!")
               return False
       return False
   ```
4. In `main()`, before calling `auto.start_program()`, check for attach flags:
   ```python
   if args.attach_window_id or args.attach:
       if not auto.attach_to_window(args.attach_window_id, args.attach):
           return 1
   else:
       if not auto.start_program():
           return 1
   ```

## Critical Safety Rules

- `attach_to_window()` must set `self.window_valid = True` immediately so existing `_check_window_valid()` calls downstream don't fail.
- `main()` must NOT call `auto.wait_for_exit()` when attaching to an already-running window (the user didn't ask us to launch it, so we shouldn't wait for it to exit). Use `args.no_wait` semantics or print "Script done. Window still active."
- Do NOT touch `focus()`, `type_text()`, `_build_keymap_cache()`, or `press_key()` internals. They remain exactly as in the original.

## Test Plan

| Step | Command | Expected |
|------|---------|---------|
| 1 | `./keypress.py --list-windows` | Note down an existing window ID, e.g. `0x03000037` |
| 2 | `./keypress.py --attach-window-id 0x03000037 -c "Attach test" -n` | Types into that window, no new program launched |
| 3 | `./keypress.py --attach "Leafpad" -c "Attach by name" -n` | Finds and types into Leafpad |
| 4 | `python3 test_loops.py && python3 test_integration.py` | 15 + 11 pass |
| 5 | `./keypress.py "leafpad" -c "Normal test" -w leafpad -n` | Still launches + types normally (regression) |

## Estimated Diff Size
~50 lines: 20 lines in `main()`, 25 lines in new `attach_to_window()` method, 5 lines in validation.

## Historical Note
An earlier version of this feature worked in tests but was bundled with compose_cache.py changes in the SAME commit. That bundling made it harder to bisect the real cause of a compose fallback bug (which turned out to be a separate `modifier` variable leak in `_build_keymap_cache()`, NOT in the attach feature itself). Do NOT bundle this with any other feature.
