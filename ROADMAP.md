# keypress Project Implementation Roadmap

> Master plan for evolving the monolithic `keypress.py` into a modular keyboard & mouse automation suite for X11 Linux.

**Constraint:** All changes must maintain backward compatibility with existing script syntax, CLI flags, and behavior.

---

## Phase 0: Architecture Planning

**Goal:** Decide the module split before writing code.

### Decision: Extract `kp_core.py` Shared Library

The monolithic `keypress.py` (~788 lines) mixes three concerns:
1. **X11 infrastructure** — display connection, window discovery, focus management
2. **Keyboard logic** — keymap caching, keycode resolution, key pressing
3. **CLI & orchestration** — argument parsing, program launching, script execution flow

We will extract a shared `kp_core.py` library so that future tools (e.g. `mouse.py`) can reuse the X11 and windowing primitives without duplicating code.

### What Goes in `kp_core.py`

| Class / Symbol | Responsibility |
|----------------|---------------|
| `X11Display` | Open/close `python-xlib` `Display`, expose `display.sync()`, handle `DISPLAY` errors, provide context-manager interface. |
| `WindowFinder` | Multi-strategy window search: by PID, by `_NET_WM_NAME` / `WM_NAME`, by `WM_CLASS`, by `WM_WINDOW_ROLE`. Return `Window` objects with validity checks. |
| `WindowController` | Focus, raise, map, set input focus, send `_NET_ACTIVE_WINDOW` EWMH client message. Also `_NET_WM_NAME` getter fallback. |
| `ProgramLauncher` | Start external program with `shlex.split` + `Popen(..., shell=False, preexec_fn=os.setsid)`, capture PID, optional stdout/stderr redirection helpers. |
| `SPECIAL_KEYS` | Constant mapping of human-readable names to X11 keycodes (moved out of `keypress.py`). |
| `KEYSYM_TO_CHAR` | Manual static keysym→char table for systems where `XK.keysym_to_string` is unreliable. |
| `cli_helpers.py` (or same module) | Reusable `argparse` helpers (e.g. `--list-windows`, `--attach`, `--attach-window-id`). |

### What Stays in `keypress.py`

| Concern | Reason |
|---------|--------|
| `KeypressAutomation` class (refactored) | Orchestrates program launch → window attach → script read → loop expand → line dispatch. Imports `kp_core` primitives. |
| `expand_script_loops()` | Pure Python parsing; stays in `keypress.py` but may be promoted to `kp_script.py` later. |
| `_get_keycode()`, `_build_keymap_cache()` | Keyboard-specific keymap caching and column handling. Could go in `kp_core` but kept in `keypress.py` because keymap semantics are keyboard-only. |
| `type_text()`, `press_key()`, `send_combo()` | Keyboard-input methods. Stay in `keypress.py`. |
| `process_line()` | Script DSL dispatch. Stays in `keypress.py`; grows in Phase 2. |
| `main()` & `argparse` setup | CLI entry point for keyboard automation. |

### What Goes in Future `mouse.py`

| Command / Feature | X11 Primitive |
|-------------------|---------------|
| `<click:x,y>` | `X.ButtonPress` / `X.ButtonRelease` via `fake_input` (button 1) |
| `<rightclick:x,y>` | `fake_input` (button 3) |
| `<dblclick:x,y>` | Two rapid button-1 sequences |
| `<move:x,y>` | `XWarpPointer` to absolute screen coordinates |
| `<drag:start:end>` | Button press → warp → move → button release |
| `<scroll:direction:amount>` | Button 4/5 (vertical) or 6/7 (horizontal) press/release |
| Mouse passthrough (optional) | Allow `<click>` inside `keypress.py` scripts by delegating to `mouse.py` or a shared `MouseController` in `kp_core.py` |

---

## Phase 1: Foundation — `kp_core.py` & `keypress.py` Refactor

**Goal:** Extract shared infrastructure, eliminate bugs, and harden window management.

**Dependencies:** None (this is the foundation).

### Tasks

- [ ] **1.1 Extract `kp_core.py`**  
  *Effort: Medium*  
  Create `kp_core.py` with `X11Display`, `WindowFinder`, `WindowController`, `ProgramLauncher`, `SPECIAL_KEYS`, `KEYSYM_TO_CHAR`. Ensure all existing imports in `keypress.py` still resolve.

- [ ] **1.2 Fix `shell=True` bug**  
  *Effort: Small*  
  In `ProgramLauncher` (and current `keypress.py`), replace `subprocess.Popen(cmd, shell=True)` with `subprocess.Popen(shlex.split(cmd), shell=False, preexec_fn=os.setsid)`.  
  **Acceptance:** Existing quoted commands (`"dosbox-x -c 'mount c'"`) still work; `pgrep -f` can locate child by exact binary name.

- [ ] **1.3 Implement multi-strategy window detection**  
  *Effort: Medium*  
  `WindowFinder` should attempt: `WM_CLASS` exact → `WM_WINDOW_ROLE` → `WM_NAME` substring → `_NET_WM_NAME` substring → `_NET_WM_PID` exact match → PID tree walk (parent→children).  
  **Acceptance:** On slow systems where window name is not set when `get_wm_name()` runs, fallback strategies still locate the window.

- [ ] **1.4 Add `--list-windows` diagnostic flag**  
  *Effort: Small*  
  Standalone CLI flag that prints all top-level windows: `WM_CLASS`, `WM_NAME`, `_NET_WM_NAME`, PID, geometry. Exits immediately.  
  **Acceptance:** Output contains at least one of class / role / name for every mapped window.

- [ ] **1.5 Add `--attach` and `--attach-window-id` flags**  
  *Effort: Small*  
  `--attach <pattern>`: skip program launch; search existing windows by pattern and attach.  
  `--attach-window-id 0x...`: skip search; attach to explicit X window ID. Mutually exclusive with positional `program`.  
  **Acceptance:** `./keypress.py --attach leafpad script.txt` finds an already-running leafpad and types into it.

- [ ] **1.6 Add `_NET_WM_NAME` fallback**  
  *Effort: Small*  
  Getter that tries `_NET_WM_NAME` first (UTF-8), then `WM_NAME` (legacy).  
  **Acceptance:** Windows with Unicode titles (e.g. LibreOffice documents) show correct names in `--list-windows` and `--attach`.

- [ ] **1.7 Add `try/finally` cleanup + `atexit`**  
  *Effort: Small*  
  Wrap main execution in `try/finally` that calls `auto.cleanup()`. Register `atexit` handler to terminate child process and close `Display` on unexpected exit.  
  **Acceptance:** Child process does not outlive `keypress.py` on `SIGTERM`, `SIGINT`, or unhandled exception.

- [ ] **1.8 Aggressive EWMH focus management**  
  *Effort: Medium*  
  Send `_NET_ACTIVE_WINDOW` client message using `send_event` when `set_input_focus` is ignored by WM.  
  **Acceptance:** In tiling WMs (i3, sway-xwayland), target window is raised and focused; `xprop -root _NET_ACTIVE_WINDOW` matches target WID after focus.

- [ ] **1.9 Refactor `keypress.py` to import from `kp_core.py`**  
  *Effort: Medium*  
  Replace inline window search, focus, and launch code with imports from `kp_core`. Keep CLI backward compatible.  
  **Acceptance:** All existing unit and integration tests pass without modification.

---

## Phase 2: Script Language Expansion

**Goal:** Make scripts programmable with variables, conditionals, loops, clipboard, and file I/O.

**Dependencies:** Phase 1 (requires stable `kp_core.py` and refactored `keypress.py`).

### Tasks

- [ ] **2.1 Create `compose_cache.py` module**  
  *Effort: Large*  
  Implement dead-key / compose sequence support. Map sequences like `dead_acute + e → é` and `Compose + " + a → ä`. Use `XGetKeyboardControl` / `XKB` if available; otherwise maintain a static compose table for common Latin-1 / Latin-3 characters. Expose `resolve_compose(sequence: str) -> List[(keycode, modifier)]`.  
  **Acceptance:** `./keypress.py "leafpad" compose.txt` where `compose.txt` contains `<compose:'+e>` types `é` on layouts with dead keys.

- [ ] **2.2 Variables: `${VARNAME}` interpolation**  
  *Effort: Medium*  
  Pre-process every script line to expand `${VARNAME}` before dispatch. Support default values: `${VAR:-default}`.  
  **Acceptance:** Script line `echo ${USER}` types the current Linux user name.

- [ ] **2.3 CLI variable assignment `-a NAME=VALUE`**  
  *Effort: Small*  
  Add `-a / --assign` repeated flag. Values are stored in a dict passed to script engine.  
  **Acceptance:** `./keypress.py "xterm" script.txt -a PASSWORD=secret123` and script contains `login ${PASSWORD}`.

- [ ] **2.4 Conditionals: `<if:condition>...<else>...</if>`**  
  *Effort: Medium*  
  Supported conditions: `var==value`, `var!=value`, `exists:window_name`, `focused`. Boolean AND/OR not required for MVP.  
  **Acceptance:** `<if:${MODE}==emulator>--emulator-mode</if>` expands to `--emulator-mode` only when variable matches.

- [ ] **2.5 While loops: `<while:condition>...</while>`**  
  *Effort: Medium*  
  Same condition grammar as `<if>`. Loop re-evaluated every iteration. Include optional `<break>` and `<continue>` tags.  
  **Acceptance:** `<while:exists:save_dialog><wait:0.5></while>` waits until save dialog disappears.

- [ ] **2.6 Clipboard access**  
  *Effort: Medium*  
  `<clipboard:get>` — types the current X11 selection (PRIMARY / CLIPBOARD).  
  `<clipboard:set:text>` — copies literal text into CLIPBOARD via `xclip` or `xsel` subprocess.  
  **Acceptance:** Script can paste clipboard content and then restore it.

- [ ] **2.7 File I/O in scripts (optional)**  
  *Effort: Large*  
  `<readfile:path:var>` reads a file into a variable. `<writefile:path:text>` writes text to file.  
  **Acceptance:** Script can read a token from `/tmp/token.txt` and type it.

---

## Phase 3: `mouse.py` Mouse Automation

**Goal:** Add pointer control as a sibling tool.

**Dependencies:** Phase 1 (requires `kp_core.py` for display and window logic).

### Tasks

- [ ] **3.1 Create `mouse.py` using `kp_core.py`**  
  *Effort: Medium*  
  New executable script, same argument style as `keypress.py`. Reuses `X11Display`, `WindowFinder`, `WindowController`, `ProgramLauncher`. Implements `MouseController` class.

- [ ] **3.2 Implement mouse commands**  
  *Effort: Medium*  
  All commands accept absolute coordinates (screen) or relative to active window if prefixed with `win:`.
  - `<click:x,y>` — single left click
  - `<rightclick:x,y>` — single right click
  - `<dblclick:x,y>` — double left click
  - `<move:x,y>` — warp pointer
  - `<drag:x1,y1:x2,y2>` — press, move, release
  - `<scroll:down:5>` — scroll down 5 notches (button 5 click-repeat)
  **Acceptance:** Each command produces the corresponding X11 event sequence verified with `xinput test` or `xev` in CI.

- [ ] **3.3 Mouse passthrough in keypress scripts (optional)**  
  *Effort: Large*  
  Allow `<click:100,200>` inside `keypress.py` script files by importing `MouseController` and dispatching through shared logic.  
  **Acceptance:** A single `keypress.py` script can type text *and* click a button coordinate before continuing.

---

## Phase 4: Testing & CI

**Goal:** Achieve >80 % coverage and CI for all new modules.

**Dependencies:** Phase 1–3 (tests are written after features).

### Tasks

- [ ] **4.1 Create `test_kp_core.py`**  
  *Effort: Medium*  
  Unit tests for `X11Display`, `WindowFinder`, `WindowController`, `ProgramLauncher` using mocked `python-xlib` objects (same pattern as `test_integration.py`).  
  **Acceptance:** Runs in headless CI without X11 display; covers error paths (missing display, invalid window ID).

- [ ] **4.2 Create `test_compose_cache.py`**  
  *Effort: Medium*  
  Tests for static compose tables and mock-based dead-key resolution.  
  **Acceptance:** All documented compose sequences have at least one test case.

- [ ] **4.3 Update `test_integration.py`**  
  *Effort: Medium*  
  Add integration tests for variables, conditionals, while loops, clipboard stubs. Keep existing loop tests intact.  
  **Acceptance:** CI job passes unchanged + new tests pass.

- [ ] **4.4 Create `test_mouse.py`**  
  *Effort: Medium*  
  Unit tests for `MouseController` event generation using mocked `fake_input` and `Xlib`. Add Xvfb integration smoke test in CI.  
  **Acceptance:** Mouse events produce correct `ButtonPress`/`ButtonRelease` sequences.

- [ ] **4.5 Update `.github/workflows/test.yml`**  
  *Effort: Small*  
  Add new jobs: `test-kp-core`, `test-compose`, `test-mouse`. Keep existing `test` job as-is but rename to `test-keypress`. Add Python matrix (3.9, 3.11, 3.12).  
  **Acceptance:** All jobs green on push / PR.

---

## Phase 5: Documentation

**Goal:** Keep docs in sync with every new feature.

**Dependencies:** All prior phases.

### Tasks

- [ ] **5.1 Update `README.md`**  
  *Effort: Medium*  
  Expand feature matrix table. Add sections for variables, conditionals, while loops, mouse, `--list-windows`, `--attach`. Update troubleshooting with new flags.

- [ ] **5.2 Update `man/keypress.1`**  
  *Effort: Small*  
  Add new flags (`-a`, `--list-windows`, `--attach`, `--attach-window-id`), new script tags (`<if>`, `<while>`, `<clipboard:*>`, `<compose:*>`).

- [ ] **5.3 Create `man/mouse.1`**  
  *Effort: Small*  
  Manual page for `mouse.py` with synopsis, commands, coordinates, environment variables (`DISPLAY`).

- [ ] **5.4 Update `examples/`**  
  *Effort: Small*  
  Add `variable_demo.txt`, `conditional_demo.txt`, `mouse_demo.txt`, `compose_demo.txt`. Verify each example runs in CI (or at least parses without error).

---

## Dependency Graph

```
┌─────────────────┐
│   Phase 0       │  Architecture decisions (no code)
└────────┬────────┘
         │
┌────────▼────────┐
│   Phase 1       │  kp_core.py + keypress.py refactor
│  (Foundation)   │  ─ prerequisite for everything
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
┌───▼───┐  ┌──▼────┐
│Phase 2│  │Phase 3│  Can be developed in parallel
│Script │  │ Mouse │  after Phase 1 is merged
│ Lang  │  │       │
└───┬───┘  └───┬───┘
    │          │
    └────┬─────┘
         │
┌────────▼────────┐
│   Phase 4       │  Tests & CI (covers Phases 1-3)
└────────┬────────┘
         │
┌────────▼────────┐
│   Phase 5       │  Documentation (final polish)
└─────────────────┘
```

---

## Backward Compatibility Checklist

Every phase must verify the following before merge:

- [ ] `./keypress.py --help` output contains all original flags and no breaking changes.
- [ ] Existing script files (e.g. `examples/leafpad_test.txt`, `examples/dosbox_commands.txt`) execute without modification.
- [ ] `<for:N>` syntax and behavior unchanged.
- [ ] `<wait:N>` syntax and behavior unchanged.
- [ ] Special keys (`<F1>`, `<Esc>`, `<Tab>`, etc.) unchanged.
- [ ] Combos (`<Ctrl+s>`, `<Alt+F4>`, etc.) unchanged.
- [ ] `-e / --emulator-mode` keycodes identical.
- [ ] CI passes with all original test jobs.

---

*Roadmap version: 1.0*  
*Last updated: 2026-06-02*
