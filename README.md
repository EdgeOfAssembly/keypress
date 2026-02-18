# keypress - Layout-Aware X11 Keyboard Automation

[![Python 3.6+](https://img.shields.io/badge/python-3.6+-blue.svg)](https://www.python.org/downloads/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![X11](https://img.shields.io/badge/platform-X11-orange.svg)](https://www.x.org/)

A keyboard automation tool that **actually respects your keyboard layout**. Unlike xdotool, keypress.py works correctly on Finnish, German, Swedish, and other non-US keyboard layouts by properly detecting and using multi-column keymaps.

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
| **Window detection** | ✅ Yes | ⚠️ Basic | ✅ **PID + Name** |
| **Multi-column keymaps** | ❌ No (0-1 only) | ❌ No | ✅ **Yes (0-7+)** |
| **Finnish/German/Swedish** | ❌ Broken | ❌ Broken | ✅ **Works** |
| **Special commands** | ❌ No | ❌ No | ✅ **`<wait>`, `<F12>`, etc.** |
| **Debug mode** | ❌ No | ❌ No | ✅ **`--debug`** |

## Features

- 🌍 **Multi-column layout support** - Works on non-US keyboards (Finnish, German, Swedish, Norwegian, etc.)
- 🎮 **Emulator mode** - Use US layout for DOSBox-X, VICE, MAME (they expect US keycodes internally)
- 📝 **Script file support** - Clean, readable syntax with special commands
- 🔍 **Auto window detection** - Find windows by PID or name pattern
- ⌨️ **Proper AltGr handling** - Automatically detects symbols like `[`, `]`, `\`, `{`, `}`, `|`
- 🐛 **Debug mode** - Inspect your keyboard mapping with `--debug`
- ⚡ **Lightweight** - Pure Python, only depends on python-xlib

## Installation

```bash
# Clone the repository
git clone https://github.com/EdgeOfAssembly/keypress.git
cd keypress
chmod +x keypress.py utils/dump_keymap.py
```

### Dependencies

**Debian/Ubuntu:**
```bash
sudo apt install python3-xlib
```

**Arch/Manjaro:**
```bash
sudo pacman -S python-xlib
```

**Fedora:**
```bash
sudo dnf install python3-xlib
```

**Gentoo:**
```bash
emerge dev-python/python-xlib
```

**Other distributions:**
```bash
pip3 install python-xlib
```

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
```

### Debug your keyboard layout
```bash
# See all keycodes and symbols
./utils/dump_keymap.py

# Find where brackets are hiding
./utils/dump_keymap.py | grep -A2 "Searching for '\['"
```

## Usage Examples

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

## Command-Line Options

```
usage: keypress.py [-h] [-c COMMAND] [-d DELAY] [-t TYPING_DELAY] 
                   [-w WINDOW] [-n] [-e] [--debug]
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
  -n, --no-wait        Exit immediately after script (don't wait for program)
  -e, --emulator-mode  Use for emulators/VMs that expect US keyboard
  --debug              Enable debug output for keyboard mapping
```

### Important Flags

**`-w, --window` (Recommended):** Specify window name to search for. More reliable than PID detection.
```bash
./keypress.py "leafpad" script.txt -w leafpad
./keypress.py "dosbox-x" dos.txt -w DOSBox
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

## Troubleshooting

### Window not found
```
WARNING: Could not find program window!
```

**Solutions:**
1. Increase startup delay: `-d 5`
2. Specify window name: `-w "leafpad"`
3. Check window name with: `xdotool search --name ""`

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
chmod +x keypress.py utils/dump_keymap.py
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

## Contributing

Contributions welcome! Please:
- Test on your keyboard layout
- Document any new layout quirks discovered
- Add examples for new use cases
- Keep the Unix philosophy: do one thing well

## Known Limitations

- **X11 only** - Does not work on Wayland (by design)
- **No dead keys** - Compose sequences (é, ñ, etc.) not supported
- **No Unicode input** - Only characters in your keymap
- **Single display** - Multi-monitor setups untested

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

## See Also

- `dump_keymap.py` - Diagnostic tool to inspect keyboard layout
- `xmodmap(1)` - Modify X11 keyboard mappings
- `setxkbmap(1)` - Set keyboard layout
- `xdotool(1)` - X11 automation (US layout only)

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