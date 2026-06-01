# Feature 03: Compose Cache Fallback in `type_text()`

## Status
**BLOCKED — requires Feature 02 merged AND deep X11 display testing**

## What It Does
When `type_text()` encounters a character that is NOT in `self.keymap_cache` (i.e., not directly typeable on the current keyboard layout), fall back to `compose_cache.ComposeCache` to look up a dead-key or compose sequence, then simulate that sequence.

## Why It's Dangerous
This feature requires the integration of THREE separate systems that must align perfectly:
1. What X11 Compose files say (e.g., `<dead_acute> <e> → "é"`)
2. What `compose_cache.py` returns (e.g., `['dead_acute', 'e']`)
3. What the Finnish keyboard's actual keycodes are for `dead_acute` (not just the character `'`, but the actual dead key at keycode 21 with modifier 0)

When these three systems don't align, you get gibberish like `caf'e na"ive` instead of `café naïve`.

## Historical Attempt and Failure
We tried to implement this. It FAILED. Here's why:

### The `modifier` variable leak bug
In `_build_keymap_cache()`, the column-scanning loop used a `modifier` variable that was set ONLY inside `if char:` (normal character caching). When a dead key keysym appeared AFTER a non-cached character on the SAME keycode iteration, `modifier` retained the value from a PREVIOUS keycode loop iteration. This caused all dead keys to be cached with wrong modifiers.

**Fix**: Move the modifier calculation BEFORE the `if char:` block, so it's set fresh for every column.

### The dead key vs regular character confusion
The original `compose_cache.py` mapped `dead_acute` to `"'"`. This meant `_get_keycode_system("'")` returned the regular apostrophe keycode, not the dead_acute keycode. On Finnish keyboard, the apostrophe key and the dead_acute key can be DIFFERENT keycodes, so pressing regular apostrophe + e produces `'e`, not `é`.

**Fix**: `compose_cache.py` must preserve dead key names (e.g., `dead_acute`) instead of mapping them to regular characters. `keypress.py` then needs a `dead_key_cache` mapping `dead_acute` → actual (keycode, modifier) discovered during keymap scanning.

## Implementation Order (Mandatory)

Because of the complexity, implement in this EXACT order across separate branches:

### Phase A (branch `feature/dead-key-cache-only`):
1. Add `DEAD_KEY_NAMES` constant mapping keysyms like `0xFE51` → `"dead_acute"`
2. In `_build_keymap_cache()`, while scanning keycodes, also populate `self.dead_key_cache[dead_name] = (keycode, modifier)`
3. Fix the `modifier` variable leak by moving modifier calculation to happen BEFORE `if char:`
4. In `_get_keycode_system()`, check `self.dead_key_cache` for dead key names AFTER special keys and BEFORE normal character lookups
5. Do NOT integrate compose_cache yet. Instead, add debug print so you can verify:
   ```python
   print(f"Dead key cache: {len(self.dead_key_cache)} entries")
   for name, (kc, mod) in sorted(self.dead_key_cache.items()):
       print(f"  {name}: keycode={kc} modifier={mod}")
   ```
6. Test Phase A on real display:
   - Run `./keypress.py --debug "leafpad" ...` and verify dead key cache shows sane keycodes
   - Finnish KC 21 should show `dead_acute: keycode=21 modifier=0` (NOT modifier=3)
   - KC 35 should show `dead_diaeresis: keycode=35 modifier=0` (NOT modifier=1)

### Phase B (branch `feature/compose-fallback`, depends on Phase A):
1. In `type_text()`, after `_get_keycode(char)` returns `(None, 0)`, try compose lookup:
   ```python
   compose_seq = compose_cache.get_sequence(char)
   if compose_seq:
       for seq_key in compose_seq:
           skc, smod = self._get_keycode(seq_key)
           if skc:
               self.press_key(skc, smod)
               time.sleep(self.typing_delay)
       continue
   ```
2. Test on real display:
   - `./keypress.py --attach-window-id 0xDEADBEEF -c "café naïve" -n`
   - MUST show `café naïve`, not `caf'e na"ive`

### Why This Order Matters
Phase A verifies that dead key keycodes are being detected and cached correctly BEFORE any compose logic is involved. If Phase A is wrong, Phase B will fail in mysterious ways and you'll blame compose when the real bug is in the keymap cache.

## Estimated Diff Size
- Phase A: ~25 lines in `_build_keymap_cache()`, ~8 lines in `_get_keycode_system()`
- Phase B: ~15 lines in `type_text()` plus import at top

## Historical Note
We tried to do `type_text()` fallback + dead_key cache + compose_cache changes ALL IN ONE session. That was a mistake. It took us 10+ back-and-forth messages to debug a simple modifier variable leak that should have been caught in Phase A. Future implementer: do not repeat our mistake.
