# keypress - Layout-Aware X11 Keyboard & Mouse Automation

[![Python 3.6+](https://img.shields.io/badge/python-3.6+-blue.svg)](https://www.python.org/downloads/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![X11](https://img.shields.io/badge/platform-X11-orange.svg)](https://www.x.org/)

A modular X11 automation suite that **actually respects your keyboard layout**. Unlike xdotool, keypress.py works correctly on Finnish, German, Swedish, and other non-US keyboard layouts by properly detecting and using multi-column keymaps.

The suite now includes:
- **keypress.py** — keyboard automation with a rich script language
- **mouse.py** — mouse automation companion
- **kp_core.py** — shared X11 library powering both tools
- **compose_cache.py** — dead-key and compose sequence support
- **script_engine.py** — unified script execution engine with variables, conditionals, and loops

## The Problem

**xdotool doesn't work with non-US keyboard layouts.** 

Try typing `path=c:\dos` on a Finnish keyboard with xdotool and you get garbage like `pöth7c;ydös` because xdotool uses hardcoded US keycodes that don't match your actual layout.

### The Discovery

While debugging why `[`, `]`, and `\` weren't working on Finnish keyboards, I discovered that:

1. Finnish keyboard layout stores these symbols in **keymap column 4** (accessed via AltGr)
2. Most tools only check columns 0-3, completely missing AltGr symbols
3. `python-xlib`'s `get_keyboard_mapping()` returns ALL columns, but nobody was using them!
4. The `xmodmap` output showed 7 columns per key, but standard documentation only mentions 4

Example from Finnish layout:
```
keycode 17 = 8 parenleft 8 parenleft bracketleft less bracketleft
             ↑ ↑         ↑ ↑         ↑           ← Column 4: AltGr+8 = [
```

**This tool scans ALL keymap columns**, properly detecting symbols wherever they hide.

## Comparison with Other Tools

| Feature | xdotool | ydotool | keypress.py |
|---------|---------|---------|-------------|
| **Layout aware** | ❌ No | ❌ No | ✅ **Yes** |
| **Emulator mode** | ❌ No | ❌ No | ✅ **Yes** |
| **AltGr support** | ⚠️ Manual | ⚠️ Manual | ✅ **Auto** |
| **Script files** | ❌ No | ❌ No | ✅ **Yes** |
| **Script variables** | ❌ No | ❌ No | ✅ **${VAR}** |
| **Conditionals** | ❌ No | ❌ No | ✅ **<if>** |
| **While loops** | ❌ No | ❌ No | ✅ **<while>** |
| **Clipboard access** | ❌ No | ❌ No | ✅ **<clipboard>** |
| **Dead-key / Compose** | ❌ No | ❌ No | ✅ **Yes** |
| **Window detection** | ✅ Yes | ⚠️ Basic | ✅ **PID + Name + Role + Class** |
| **Multi-strategy search** | ❌ No | ❌ No | ✅ **class→role→name** |
| **Attach to running app** | ❌ No | ❌ No | ✅ **--attach** |
| **List windows** | ❌ No | ❌ No | ✅ **--list-windows** |
| **Mouse automation** | ✅ Yes | ❌ No | ✅ **mouse.py** |
| **Multi-column keymaps** | ❌ No (0-1 only) | ❌ No | ✅ **Yes (0-7+)** |
| **Finnish/German/Swedish** | ❌ Broken | ❌ Broken | ✅ **Works** |
| **Special commands** | ❌ No | ❌ No | ✅ **`<wait>`, `<F12>`, etc.** |
| **Debug mode** | ❌ No | ❌ No | ✅ **`--debug`** |

## Features

- 🌍 **Multi-column layout support** - Works on non-US keyboards (Finnish, German, Swedish, Norwegian, etc.)
- 🎮 **Emulator mode** - Use US layout for DOSBox-X, VICE, MAME (they expect US keycodes internally)
- 📝 **Rich script language** - Variables, conditionals, while-loops, for-loops, clipboard, wait commands
- 🖱️ **Mouse automation** - Click, drag, scroll via `mouse.py`
- 🔗 **Compose / dead-key support** - Type é, ñ, ç, —, € and more via X11 Compose sequences
- 🔍 **Auto window detection** - Find windows by PID, name pattern, role, or WM class
- 🔗 **Multi-strategy fallback** - Searches class → role → name automatically
- ⌨️ **Proper AltGr handling** - Automatically detects symbols like `[`, `]`, `\`, `{`, `}`, `|`
- 🐛 **Debug mode** - Inspect your keyboard mapping with `--debug`
- ⚡ **Lightweight** - Pure Python, only depends on python-xlib (+ xclip/xsel for clipboard)

## Architecture

```
┌─────────────────┐     ┌─────────────────┐
│   keypress.py   │     │     mouse.py    │
│  (keyboard)     │     │   (mouse)       │
└────────┬────────┘     └────────┬────────┘
         │                         │
         └───────────┬─────────────┘
                     │
              ┌──────┴──────┐
              │  kp_core.py  │
              │  (shared X11 │
              │   library)   │
              └──────┬──────┘
                     │
         ┌───────────┴───────────┐
         │                       │
┌────────┴────────┐     ┌────────┴────────┐
│ script_engine.py│     │ compose_cache.py│
│ (loops/vars/    │     │ (dead keys &    │
│  conditionals)  │     │  compose seqs)  │
└─────────────────┘     └─────────────────┘
```

**kp_core.py** is the shared foundation providing:
- `X11Display` — lazy X11 connection
- `WindowFinder` — search by class, role, name, PID; list all windows
- `WindowController` — focus, raise, validate windows
- `ProgramLauncher` — launch and clean up child processes
- CLI argument helpers used by both `keypress.py` and `mouse.py`

## Installation

```bash
# Clone the repository
git clone https://github.com/EdgeOfAssembly/keypress.git
cd keypress
chmod +x keypress.py mouse.py utils/dump_keymap.py
```

### Dependencies

**Debian/Ubuntu:**
```bash
sudo apt install python3-xlib xclip
```

**Arch/Manjaro:**
```bash
sudo pacman -S python-xlib xclip
```

**Fedora:**
```bash
sudo dnf install python3-xlib xclip
```

**Gentoo:**
```bash
emerge dev-python/python-xlib x11-misc/xclip
```

**Other distributions:**
```bash
pip3 install python-xlib
# Also install xclip (or xsel) for clipboard support
```

No separate installation is needed for `compose_cache.py` or `script_engine.py`; they are imported automatically.

## Quick Start

### Normal apps (respects your keyboard layout)
```bash
./keypress.py "leafpad" examples/leafpad_test.txt -w leafpad
./keypress.py "gedit" script.txt -w gedit
./keypress.py "xterm" commands.txt -w xterm
```

### Emulators (use US layout internally)
```bash
./keypress.py "dosbox-x" examples/dosbox_commands.txt -w DOSBox --emulator-mode
./keypress.py "vice" game_commands.txt -w VICE --emulator-mode
```

### Quick commands
```bash
# Type a single line
./keypress.py "leafpad" -c "Hello World!" -c "<Ctrl+s>" -w leafpad

# Multiple commands
./keypress.py "xterm" -c "ls -la" -c "pwd" -w xterm

# Set script variables
./keypress.py "leafpad" script.txt -w leafpad -a USER=admin -a MODE=debug
```

### Attach to an already-running program
```bash
./keypress.py "gedit" script.txt --attach 12345 -w gedit
./keypress.py "leafpad" -c "<Ctrl+s>" --attach-window-id 0x2a00003
```

### List windows to find the right name
```bash
./keypress.py --list-windows
```

### Mouse automation
```bash
./mouse.py "leafpad" mouse_script.txt -w leafpad
./mouse.py --attach leafpad -c "<click:100,200>"
```

### Debug your keyboard layout
```bash
# See all keycodes and symbols
./utils/dump_keymap.py

# Find where brackets are hiding
./utils/dump_keymap.py | grep -A2 "Searching for '\['"
```

## Script File Format

### Basic Text
Each line is typed and followed by Enter automatically:
```
dir /p
echo "Hello"
cd test
```

### Special Keys
Use `<keyname>` for special keys:
```
<Esc>              # Escape key
<F1>               # Function keys
<Tab>
<Backspace>
<Delete>
<Up> <Down> <Left> <Right>
<Home> <End>
<PageUp> <PageDown>
```

### Key Combinations
Use `+` to combine keys:
```
<Ctrl+c>           # Copy
<Ctrl+v>           # Paste
<Alt+F4>           # Close window
<Shift+Insert>     # Alternative paste
<F12+f>            # Custom combo (for emulators)
```

### Special Commands

**No Enter after previous line:**
```
echo "No enter after this"
<nowait>
<Space>
```

**Wait/delay:**
```
<wait:2>           # Wait 2 seconds
<wait:0.5>         # Wait 500ms
```

**Loop blocks:**
```
<for:3>
<Tab>
<Enter>
</for>
```

Repeats the enclosed block exactly `N` times (N must be an integer ≥ 1).
Loops can be nested:

```
<for:2>
<for:3>
hello
</for>
</for>
```

The above types "hello" 6 times (2 × 3).

**Comments:**
```
# This is a comment
dir              # Inline comments work too
```

### Complete Example
```
# Login script
<wait:2>
username
<Tab>
password123
<Return>

# Wait for app to load
<wait:3>

# Type command
dir /p
<wait:1>

# Save and exit
<Ctrl+s>
<Alt+F4>
```

## New Script Language Syntax

### Variables

Pass variables with `-a NAME=VALUE` on the command line, then use `${NAME}` in scripts.

```text
Hello ${USERNAME}
Path: ${OUTPUT_DIR}/file.txt
Default: ${MODE:-normal}
```

Variable syntax supports defaults:
- `${VAR}` — replaced with value, or left as-is if undefined
- `${VAR:-default}` — replaced with value, or `default` if undefined
- `$$` — literal dollar sign

**Command line:**
```bash
./keypress.py "leafpad" script.txt -w leafpad \
    -a USERNAME=finn \
    -a OUTPUT_DIR=/tmp \
    -a MODE=debug
```

### Conditionals

Use `<if:condition>` ... `<else>` ... `</if>` for branching.

```text
<if:var_defined("MODE")>
    Mode is ${MODE}
<else>
    No mode set
</if>
```

Supported conditions:
- `var_defined("NAME")` — true if variable was set
- `eq("NAME","value")` — true if variable equals value
- `ne("NAME","value")` — true if variable does not equal value
- `window_exists("pattern")` — true if a window with that name exists
- `clipboard_empty` — true if clipboard has no text
- `true` / `false` — literal booleans
- `not:...` — negate any condition

### While Loops

Poll a condition with optional timeout.

```text
<while:timeout:5:not:window_exists("Save Dialog")>
    <wait:0.5>
</while>
```

Syntax: `<while:timeout:SECONDS:CONDITION>` ... `</while>`

Use `<break>` to exit a while loop early:
```text
<while:true>
    <wait:1>
    <if:window_exists("Done")>
        <break>
    </if>
</while>
```

### Clipboard

Read or write the X11 clipboard inside a script:

```text
<clipboard:get>       # Paste clipboard content as keystrokes
<clipboard:set:hello world>   # Set clipboard text
```

Requires `xclip` or `xsel` to be installed.

## Command-Line Options

### keypress.py

```
usage: keypress.py [-h] [-c COMMAND] [-d DELAY] [-t TYPING_DELAY] 
                   [-w WINDOW] [-n] [-e] [--debug]
                   [--list-windows] [--attach PID]
                   [--attach-window-id ID] [-a NAME=VALUE]
                   [--compose-key KEY] [--window-strategy STRATEGY]
                   program [script]

positional arguments:
  program              Program to launch (in quotes if has args)
  script               Script file to execute

optional arguments:
  -h, --help           Show this help message and exit
  -c, --command        Execute single command (can be repeated)
  -d, --delay          Startup delay in seconds (default: 2.0)
  -t, --typing-delay   Delay between keystrokes (default: 0.03)
  -w, --window         Window name pattern to search for (recommended)
  --window-strategy    Search strategy: class, role, name, pid, all (default: class)
  -n, --no-wait        Exit immediately after script (don't wait for program)
  -e, --emulator-mode  Use for emulators/VMs that expect US keyboard
  --debug              Enable debug output for keyboard mapping
  --list-windows       List all visible X11 windows and exit
  --attach PID         Attach to already-running process by PID
  --attach-window-id ID
                       Attach to existing window by ID (hex or decimal)
  -a, --arg            Set script variable NAME=VALUE (repeatable)
  --compose-key KEY    Key to use as compose key (default: Alt_R)
```

### mouse.py

```
usage: mouse.py [-h] [-c COMMAND] [-d DELAY] [-t TYPING_DELAY]
                [-w WINDOW] [-n] [--debug]
                [--list-windows] [--attach PID]
                [--attach-window-id ID] [--window-strategy STRATEGY]
                [program] [script]
```

Mouse script commands:
- `<click:100,200>` — Left click at screen coordinates (100, 200)
- `<rightclick:100,200>` — Right click at coordinates
- `<dblclick:100,200>` — Double click at coordinates
- `<move:100,200>` — Move cursor to coordinates
- `<drag:100,200:500,600>` — Drag from (100,200) to (500,600)
- `<scroll:up:3>` — Scroll up 3 clicks
- `<scroll:down:5>` — Scroll down 5 clicks
- `<wait:2>` — Wait 2 seconds
- `# comment` — Ignored

## Important Flags

**`-w, --window` (Recommended):** Specify window name to search for. More reliable than PID detection.
```bash
./keypress.py "leafpad" script.txt -w leafpad
./keypress.py "dosbox-x" dos.txt -w DOSBox
```

**`--window-strategy` (Multi-strategy fallback):** Controls how windows are matched.
```bash
# Try class, then role, then name
./keypress.py "myapp" script.txt -w myapp --window-strategy all

# Search by role only
./keypress.py "myapp" script.txt -w myapp --window-strategy role
```

**`--list-windows` (Diagnostic):** Show all X11 windows so you know what `-w` value to use.
```bash
./keypress.py --list-windows
# Output:
# 0x02a00003  Leafpad              PID=12345  leafpad
# 0x04c0000a  Gedit                PID=12367  test.txt - gedit
```

**`--attach` (Already-running programs):** Skip launching and attach to an existing process by PID.
```bash
./keypress.py "gedit" script.txt --attach 12345 -w gedit
```

**`--attach-window-id` (By X11 ID):** Attach directly to an X11 window ID (hex or decimal).
```bash
./keypress.py "leafpad" -c "<Ctrl+s>" --attach-window-id 0x2a00003
```

**`-a, --arg` (Script variables):** Define variables that can be referenced with `${NAME}` in scripts.
```bash
./keypress.py "leafpad" script.txt -w leafpad -a USER=admin -a PATH=/home/user
```

**`--compose-key` (Dead-key / Compose):** Set which key acts as the compose key for typing characters via compose sequences.
```bash
# Default is Alt_R; set to Right Ctrl instead
./keypress.py "gedit" script.txt -w gedit --compose-key Control_R
```

**`-e, --emulator-mode` (For Emulators):** Use hardcoded US layout instead of system layout. Required for DOSBox-X, VICE, MAME, etc.
```bash
./keypress.py "dosbox-x" script.txt -w DOSBox --emulator-mode
```

**`-d, --delay` (Slow Systems):** Increase startup delay if window isn't found.
```bash
./keypress.py "dosbox-x" script.txt -w DOSBox -d 5
```

**`--debug` (Troubleshooting):** See what characters are detected in your layout.
```bash
./keypress.py "leafpad" script.txt --debug
```

## How It Works

1. **Queries X11 keyboard mapping** using `python-xlib`'s `get_keyboard_mapping()`
2. **Scans ALL columns** (not just 0-3) to find characters in multi-column layouts
3. **Maps column index to modifiers:**
   - Column 0 = Normal key
   - Column 1 = Shift
   - Column 2/4 = AltGr
   - Column 3/5 = Shift+AltGr
   - Column 6+ = Treated as AltGr variants
4. **Builds a cache** of character → (keycode, modifier) mappings
5. **Uses `fake_input`** to send proper keycode+modifier combinations to the target window

For characters not found in the keymap (e.g., é, ñ, €), `compose_cache.py` parses the system's X11 Compose file and generates the appropriate dead-key / compose-key sequence.

### Normal Mode vs Emulator Mode

**Normal Mode (Default):**
- Reads your system's X11 keyboard layout
- Respects your language (Finnish, German, Swedish, etc.)
- Types symbols exactly as they appear on your keyboard
- Perfect for: text editors, terminals, normal apps

**Emulator Mode (`--emulator-mode`):**
- Uses hardcoded US keyboard layout
- Ignores your system layout
- Sends US keycodes directly
- Perfect for: DOSBox-X, VICE, MAME, other emulators that run US DOS/games internally

## Examples

### Example 1: DOS Automation
```bash
./keypress.py "dosbox-x" dos_script.txt -w DOSBox --emulator-mode -d 3
```

**dos_script.txt:**
```
mount c ~/dos
c:
dir
cd games
edit readme.txt
```

### Example 2: Text Editor Automation
```bash
./keypress.py "leafpad /tmp/output.txt" test.txt -w leafpad
```

**test.txt:**
```
Testing symbols: [ ] \ { } |
Path: C:\Program Files\Test
<Ctrl+s>
```

### Example 3: Terminal Commands
```bash
./keypress.py "xterm" -c "echo 'Automated command'" -w xterm -n
```

### Example 4: Variable Demo
**variable_demo.txt:**
```
Hello, ${USERNAME}!
<if:eq("MODE","debug")>
    Debug mode is ON
<else>
    Debug mode is OFF
</if>
Output path: ${OUTPUT_DIR:-/tmp}/report.txt
```

Run with:
```bash
./keypress.py "leafpad" variable_demo.txt -w leafpad \
    -a USERNAME=EdgeOfAssembly -a MODE=debug -a OUTPUT_DIR=/home/user
```

### Example 5: Conditional Demo
**conditional_demo.txt:**
```
<if:var_defined("FAST_MODE")>
    <wait:0.1>
<else>
    <wait:2>
</if>
Starting process...
<if:window_exists("Error Dialog")>
    <Alt+F4>
</if>
```

### Example 6: Mouse Automation
**mouse_script.txt:**
```
<click:100,200>
<wait:0.5>
<dblclick:300,400>
<wait:0.5>
<drag:100,200:500,600>
<wait:0.5>
<scroll:down:3>
```

Run with:
```bash
./mouse.py "leafpad" mouse_script.txt -w leafpad
```

### Example 7: Compose Sequence Demo (Finnish / International)
**compose_demo.txt:**
```
# Dead-key characters now supported!
Resume: cafe with creme brulee is 10 euro
Price: 50 cent
<Return>
Temperature: 25 degrees
---
```

Run with:
```bash
./keypress.py "gedit" compose_demo.txt -w gedit --compose-key Alt_R
```

**Note on Finnish keyboards:** If `Alt_R` is your AltGr, you can often use it as the compose key. If dead keys aren't working, verify your compose file exists:
```bash
ls /usr/share/X11/locale/en_US.UTF-8/Compose
```

### Example 8: While Loop — Wait for Window
**wait_dialog.txt:**
```
<click:500,300>
<wait:1>
<while:timeout:10:not:window_exists("Confirm Save")>
    <wait:0.5>
</while>
<if:window_exists("Confirm Save")>
    <Tab>
    <Return>
</if>
```

## Troubleshooting

### Window not found
```
WARNING: Could not find program window!
```

**Solutions:**
1. Increase startup delay: `-d 5`
2. Specify window name: `-w "leafpad"`
3. Use `--list-windows` to see exact window names:
   ```bash
   ./keypress.py --list-windows
   ```
4. Use multi-strategy search: `--window-strategy all`
5. Attach to an already-running instance:
   ```bash
   pgrep -f leafpad
   ./keypress.py "leafpad" script.txt --attach 12345 -w leafpad
   ```

### Characters not typing correctly

**In normal apps (leafpad, gedit):**
- Don't use `--emulator-mode`
- Run `./utils/dump_keymap.py` to verify your layout is detected
- Use `--debug` to see what's cached

**In emulators (DOSBox-X, VICE):**
- MUST use `--emulator-mode`
- Emulators expect US keyboard layout internally

### Some symbols missing

Run the diagnostic tool:
```bash
./utils/dump_keymap.py | grep "Searching for"
```

If symbols are NOT FOUND, they're not in your X11 keymap. Check your keyboard layout:
```bash
setxkbmap -query
xmodmap -pke | grep bracketleft
```

### Dead-key characters not working (é, ñ, €, etc.)

1. Make sure `xclip` is installed (used for clipboard fallback too)
2. Check that an X11 Compose file exists:
   ```bash
   ls /usr/share/X11/locale/en_US.UTF-8/Compose
   # or
   ls ~/.XCompose
   ```
3. Set the correct compose key for your layout:
   ```bash
   ./keypress.py "gedit" script.txt -w gedit --compose-key Alt_R
   ```
   On many Finnish keyboards, `Alt_R` (AltGr) is the compose key.
4. If your layout uses `ISO_Level3_Shift` instead, try `--compose-key ISO_Level3_Shift`

### Finnish / German / Swedish Specific Tips

This tool was literally built for Finnish keyboards! 🇫🇮

- **Finnish layout:** `[` is on `AltGr+8`, `]` on `AltGr+9`, `{` on `AltGr+Shift+8`. These live in **column 4/5** of the keymap and are detected automatically.
- **German layout:** `@` is `AltGr+q`, `\` is `AltGr+ß`. Enable `--debug` to confirm they are mapped.
- **Swedish layout:** Similar to Finnish; `[` and `]` are also on `AltGr+8/9`.
- If you use the `fi`, `de`, or `se` XKB layouts and symbols still fail, run:
  ```bash
  setxkbmap -layout fi
  ./utils/dump_keymap.py
  ```

### Wayland not supported

This tool requires X11. If you're on Wayland:
```bash
# Check if you're on Wayland
echo $XDG_SESSION_TYPE

# Switch to X11 (varies by distribution)
# Usually: log out, choose "X11 session" at login screen
```

### Permission denied

Make scripts executable:
```bash
chmod +x keypress.py mouse.py utils/dump_keymap.py
```

## Real-World Use Cases

### 1. DOSBox-X Automation
Automate installation of DOS games and software:
```bash
./keypress.py "dosbox-x" install_game.txt -w DOSBox --emulator-mode
```

### 2. GUI Testing
Test text editors, terminals, and apps:
```bash
for script in tests/*.txt; do
    ./keypress.py "myapp" "$script" -w MyApp
done
```

### 3. Demo Recording
Create reproducible demos with precise timing:
```bash
./keypress.py "xterm" demo.txt -t 0.1  # Slow typing for visibility
```

### 4. Accessibility
Pre-programmed sequences for users with mobility challenges:
```bash
./keypress.py "firefox" browse_sequence.txt -w Firefox
```

### 5. Clipboard-Driven Automation
Fetch dynamic content and paste it:
```bash
echo "Build #42 passed" | xclip -selection clipboard
./keypress.py "gedit" -c "<clipboard:get>" -w gedit
```

## Contributing

Contributions welcome! Please:
- Test on your keyboard layout
- Document any new layout quirks discovered
- Add examples for new use cases
- Keep the Unix philosophy: do one thing well

## Known Limitations

- **X11 only** - Does not work on Wayland (by design)
- **Single display** - Multi-monitor setups untested
- **Clipboard requires xclip/xsel** - Install one of these for clipboard commands

## Technical Details

### Why Column 4?

From the [X Keyboard Extension specification](https://www.x.org/releases/X11R7.7/doc/kbproto/xkbproto.html), keysym columns are organized as:

```
Column  Modifier      Example (Finnish)
------  --------      -----------------
0       None          8
1       Shift         (
2       Mode_switch   8 (duplicate)
3       Mode+Shift    (
4       ISO_Level3    [    ← AltGr symbols here!
5       Level3+Shift  <
6       (extended)    [
```

The X11 core protocol documentation mentions 4 columns, but XKB allows up to 8+ columns. Finnish layout uses column 4 for AltGr, which most tools miss!

### Python-xlib API

The key function is `get_keyboard_mapping(min_keycode, count)`:
```python
from Xlib import display

d = display.Display()
min_kc, max_kc = 8, 255
keymap = d.get_keyboard_mapping(min_kc, max_kc - min_kc + 1)

# keymap is a list of tuples, one per keycode
# Each tuple contains keysyms for different modifier states
for keycode in range(min_kc, max_kc + 1):
    keysyms = keymap[keycode - min_kc]
    # keysyms can have 4, 6, 8, or more elements!
```

Most examples only check `keysyms[0:4]`, missing extended layouts. This tool checks ALL elements.

## File Listing

```
keypress.py          | main keyboard automation script
mouse.py             | mouse automation companion
kp_core.py           | shared X11 library (display, window finder, launcher)
compose_cache.py     | dead-key compose sequence support
script_engine.py     | unified script execution engine (loops, vars, if/while)
test_*.py            | test suite (6 files, 135+ tests)
examples/            | example scripts
utils/dump_keymap.py | keyboard layout diagnostic
man/                 | man pages
```

## See Also

- `dump_keymap.py` - Diagnostic tool to inspect keyboard layout
- `xmodmap(1)` - Modify X11 keyboard mappings
- `setxkbmap(1)` - Set keyboard layout
- `xdotool(1)` - X11 automation (US layout only)
- `xclip(1)` / `xsel(1)` - Clipboard utilities

## Author

**EdgeOfAssembly**
- Email: haxbox2000@gmail.com
- GitHub: https://github.com/EdgeOfAssembly

## License

GNU General Public License v3.0 (GPL-3.0)

See [LICENSE](LICENSE) for full text.

## Acknowledgments

- The python-xlib developers for the excellent X11 bindings
- The X.Org Foundation for X11 documentation
- Everyone struggling with non-US keyboard layouts - this one's for you! 🇫🇮🇩🇪🇸🇪
