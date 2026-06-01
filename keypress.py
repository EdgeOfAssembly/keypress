#!/usr/bin/env python3
"""
Generic X11 Keypress Automation Script

Usage:
    ./keypress.py "program --args" script.txt
    ./keypress.py "dosbox-x ..." script.txt --emulator-mode
"""

import subprocess
import time
import sys
import argparse
import re

from kp_core import (
    SPECIAL_KEYS, KEYSYM_TO_CHAR,
    X11Display, WindowFinder, WindowController, ProgramLauncher,
)
from compose_cache import ComposeCache
import script_engine as se

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


class KeypressAutomation:
    SPECIAL_KEYS = SPECIAL_KEYS
    KEYSYM_TO_CHAR = KEYSYM_TO_CHAR

    # Layout-independent US keyboard mapping (for emulator mode)
    # Format: character -> (keycode, needs_shift)
    US_KEYMAP = {
        # Letters (lowercase)
        'a': (38, False), 'b': (56, False), 'c': (54, False), 'd': (40, False),
        'e': (26, False), 'f': (41, False), 'g': (42, False), 'h': (43, False),
        'i': (31, False), 'j': (44, False), 'k': (45, False), 'l': (46, False),
        'm': (58, False), 'n': (57, False), 'o': (32, False), 'p': (33, False),
        'q': (24, False), 'r': (27, False), 's': (39, False), 't': (28, False),
        'u': (30, False), 'v': (55, False), 'w': (25, False), 'x': (53, False),
        'y': (29, False), 'z': (52, False),

        # Letters (uppercase)
        'A': (38, True), 'B': (56, True), 'C': (54, True), 'D': (40, True),
        'E': (26, True), 'F': (41, True), 'G': (42, True), 'H': (43, True),
        'I': (31, True), 'J': (44, True), 'K': (45, True), 'L': (46, True),
        'M': (58, True), 'N': (57, True), 'O': (32, True), 'P': (33, True),
        'Q': (24, True), 'R': (27, True), 'S': (39, True), 'T': (28, True),
        'U': (30, True), 'V': (55, True), 'W': (25, True), 'X': (53, True),
        'Y': (29, True), 'Z': (52, True),

        # Numbers
        '0': (19, False), '1': (10, False), '2': (11, False), '3': (12, False),
        '4': (13, False), '5': (14, False), '6': (15, False), '7': (16, False),
        '8': (17, False), '9': (18, False),

        # Symbols (unshifted)
        ' ': (65, False), '-': (20, False), '=': (21, False),
        '[': (34, False), ']': (35, False), '\\': (51, False),
        ';': (47, False), "'": (48, False), '`': (49, False),
        ',': (59, False), '.': (60, False), '/': (61, False),

        # Symbols (shifted)
        '!': (10, True), '@': (11, True), '#': (12, True), '$': (13, True),
        '%': (14, True), '^': (15, True), '&': (16, True), '*': (17, True),
        '(': (18, True), ')': (19, True), '_': (20, True), '+': (21, True),
        '{': (34, True), '}': (35, True), '|': (51, True),
        ':': (47, True), '"': (48, True), '~': (49, True),
        '<': (59, True), '>': (60, True), '?': (61, True),
    }

    def __init__(self, program_cmd, startup_delay=2.0, typing_delay=0.03,
                 window_name=None, emulator_mode=False, debug=False,
                 attach_pid=None, attach_window_id=None, compose_key='Alt_R'):
        self.program_cmd = program_cmd
        self.startup_delay = startup_delay
        self.typing_delay = typing_delay
        self.window_name = window_name
        self.emulator_mode = emulator_mode
        self.debug = debug
        self.attach_pid = attach_pid
        self.attach_window_id = attach_window_id

        self.x11 = X11Display()
        self.display = self.x11.display
        self.finder = WindowFinder(self.x11)
        self.controller = WindowController(self.x11)
        self.launcher = ProgramLauncher()

        self.process = None
        self.window = None
        self.window_valid = False
        self.keymap_cache = {}
        self.compose_cache = None
        self.script_vars = {}

        if emulator_mode:
            print("Mode: Emulator (US layout for DOSBox-X, VICE, etc.)")
        else:
            print("Mode: Normal (respects your system keyboard layout)")
            self._build_keymap_cache()
            self.compose_cache = ComposeCache(compose_key=compose_key)

    def _get_keycode_range(self):
        """Get keycode range from the X11 display."""
        return self.x11._get_keycode_range()

    def _keysym_to_char(self, keysym):
        """Convert keysym to character, using manual mapping if needed"""
        if keysym in self.KEYSYM_TO_CHAR:
            return self.KEYSYM_TO_CHAR[keysym]

        from Xlib import XK
        char = XK.keysym_to_string(keysym)
        if char and len(char) == 1:
            return char

        return None

    def _build_keymap_cache(self):
        """Build a cache of character -> (keycode, modifiers) from actual keyboard layout"""
        print("Building keyboard map from system layout...")

        min_keycode, max_keycode = self._get_keycode_range()
        print(f"Keycode range: {min_keycode}-{max_keycode}")

        try:
            keymap = self.display.get_keyboard_mapping(min_keycode, max_keycode - min_keycode + 1)
        except Exception as e:
            print(f"Warning: Could not get keyboard mapping: {e}")
            print("Falling back to emulator mode behavior")
            self.keymap_cache = {}
            return

        if self.debug:
            print("\n=== DEBUG: Scanning for bracket/backslash keysyms ===")

        for keycode in range(min_keycode, max_keycode + 1):
            index = keycode - min_keycode
            if index >= len(keymap):
                continue

            keysyms = keymap[index]
            if not keysyms:
                continue

            if self.debug:
                for col_idx, keysym in enumerate(keysyms):
                    if keysym != 0:
                        char = self._keysym_to_char(keysym)
                        if keysym in [0x5b, 0x5d, 0x5c, 0x7b, 0x7d, 0x7c]:
                            print(f"  Keycode {keycode}, col {col_idx}: keysym={hex(keysym)}, char='{char}'")

            for col in range(len(keysyms)):
                keysym = keysyms[col]
                if keysym == 0:
                    continue

                char = self._keysym_to_char(keysym)
                if char:
                    if char not in self.keymap_cache:
                        if col == 0:
                            modifier = 0
                        elif col == 1:
                            modifier = 1
                        elif col in (2, 4):
                            modifier = 2
                        elif col in (3, 5):
                            modifier = 3
                        else:
                            modifier = 2

                        self.keymap_cache[char] = (keycode, modifier)

        if self.debug:
            print("=== Cached characters ===")
            for char in sorted(self.keymap_cache.keys()):
                if char in ['[', ']', '\\', '{', '}', '|', '/']:
                    keycode, mod = self.keymap_cache[char]
                    mod_name = ['none', 'shift', 'altgr', 'shift+altgr'][mod]
                    print(f"  '{char}': keycode={keycode}, modifier={mod_name}")

        print(f"Keyboard map built: {len(self.keymap_cache)} characters mapped")

    def start_program(self):
        """Start the target program"""
        print(f"Starting: {self.program_cmd}")
        self.launcher.launch(self.program_cmd)

        print(f"Process PID: {self.launcher.pid}")
        print(f"Waiting {self.startup_delay}s for program window...")
        time.sleep(self.startup_delay)

        if self.window_name:
            self.window = self.finder.find(self.window_name, strategy='name')
        else:
            self.window = self.finder.find_by_pid(self.launcher.pid)

        if self.window:
            wid = hex(self.window.id)
            try:
                name = self.window.get_wm_name() or "Unknown"
            except:
                name = "Unknown"
            print(f"Found window: {wid} - {name}")
            self.window_valid = True
            time.sleep(0.5)
            return True
        else:
            print("WARNING: Could not find program window!")
            print("Keypresses will not work. Try:")
            print(f"  1. Increase delay: -d 5")
            print(f"  2. Specify window name: -w 'window_name'")
            return False

    def _check_window_valid(self):
        """Check if window is still valid"""
        if not self.window:
            return False

        if not self.controller.is_valid(self.window):
            self.window_valid = False
            return False
        return True

    def focus(self):
        """Focus the target window"""
        if not self.window or not self._check_window_valid():
            return False

        try:
            result = self.controller.focus(self.window)
            time.sleep(0.05)
            if not result:
                self.window_valid = False
            return result
        except Exception as e:
            print(f"Warning: Could not focus window: {e}")
            self.window_valid = False
            return False

    def _get_keycode_us(self, key_name):
        """Convert key name to keycode using US layout - returns (keycode, modifier)"""
        key_lower = key_name.lower()

        if key_lower in self.SPECIAL_KEYS:
            return (self.SPECIAL_KEYS[key_lower], 0)

        if len(key_name) == 1 and key_name in self.US_KEYMAP:
            keycode, needs_shift = self.US_KEYMAP[key_name]
            return (keycode, 1 if needs_shift else 0)

        return (None, 0)

    def _get_keycode_system(self, key_name):
        """Convert key name to keycode using system layout - returns (keycode, modifier)"""
        key_lower = key_name.lower()

        if key_lower in self.SPECIAL_KEYS:
            return (self.SPECIAL_KEYS[key_lower], 0)

        if len(key_name) == 1:
            if key_name in self.keymap_cache:
                return self.keymap_cache[key_name]
            else:
                return (None, 0)

        return (None, 0)

    def _get_keycode(self, key_name):
        """Get keycode based on selected layout mode"""
        if self.emulator_mode:
            return self._get_keycode_us(key_name)
        else:
            return self._get_keycode_system(key_name)

    def press_key(self, keycode, modifier=0):
        """Press and release a single key by keycode with modifiers
        modifier: 0=none, 1=shift, 2=altgr, 3=shift+altgr
        """
        try:
            from Xlib import X
            from Xlib.ext.xtest import fake_input

            if modifier in (1, 3):
                fake_input(self.display, X.KeyPress, 50)
            if modifier in (2, 3):
                fake_input(self.display, X.KeyPress, 108)

            fake_input(self.display, X.KeyPress, keycode)
            self.display.flush()
            time.sleep(0.05)
            fake_input(self.display, X.KeyRelease, keycode)
            self.display.sync()

            if modifier in (2, 3):
                fake_input(self.display, X.KeyRelease, 108)
            if modifier in (1, 3):
                fake_input(self.display, X.KeyRelease, 50)

            time.sleep(0.05)
            return True
        except Exception as e:
            print(f"Warning: Key press failed: {e}")
            return False

    def send_combo(self, combo_str):
        """Send key combination like 'Ctrl+Alt+Del' or 'F12+f'"""
        if not self.focus():
            return False

        from Xlib import X
        from Xlib.ext.xtest import fake_input

        keys = [k.strip() for k in combo_str.split('+')]
        key_info = []

        for key in keys:
            keycode, modifier = self._get_keycode(key)
            if keycode:
                key_info.append(keycode)
            else:
                print(f"Warning: Unknown key '{key}' in combo '{combo_str}'")
                return False

        try:
            for keycode in key_info:
                fake_input(self.display, X.KeyPress, keycode)
                self.display.sync()
                time.sleep(0.05)

            for keycode in reversed(key_info):
                fake_input(self.display, X.KeyRelease, keycode)
                self.display.sync()
                time.sleep(0.05)
            return True
        except Exception as e:
            print(f"Warning: Combo failed: {e}")
            return False

    def _type_compose_sequence(self, sequence):
        """Type a character via compose sequence.
        
        sequence: list of X11 key names, e.g., ['dead_acute', 'e'] for 'é'
        """
        for key in sequence:
            keycode, modifier = self._get_keycode(key)
            if keycode:
                self.press_key(keycode, modifier)
                time.sleep(0.05)
            else:
                print(f"Warning: Cannot type compose key '{key}'")

    def type_text(self, text):
        """Type a string of text"""
        if not self.focus():
            return False

        for char in text:
            keycode, modifier = self._get_keycode(char)

            if keycode:
                try:
                    self.press_key(keycode, modifier)
                    time.sleep(self.typing_delay)
                except Exception as e:
                    print(f"Warning: Failed to type '{char}': {e}")
                continue

            seq = self.compose_cache.get_sequence(char) if self.compose_cache else None
            if seq:
                print(f"  [compose: {char}]")
                self._type_compose_sequence(seq)
                continue

            print(f"Warning: Cannot type character '{char}' (not in current layout, skipping)")
            continue

        return True

    def _expand_variables(self, line, vars_dict):
        """Expand ${VARNAME} placeholders in *line*."""
        if not vars_dict:
            return line

        def _replace(match):
            name = match.group(1)
            return vars_dict.get(name, match.group(0))

        return re.sub(r'\$\{(.+?)\}', _replace, line)

    def _handle_clipboard_get(self):
        """Type current clipboard content."""
        try:
            result = subprocess.run(
                ['xclip', '-selection', 'clipboard', '-o'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout:
                self.type_text(result.stdout)
        except Exception:
            pass

    def _handle_clipboard_set(self, text):
        """Set clipboard to *text*."""
        try:
            subprocess.run(
                ['xclip', '-selection', 'clipboard'],
                input=text.encode(), check=True
            )
        except Exception:
            try:
                subprocess.run(
                    ['xsel', '--clipboard', '--input'],
                    input=text.encode(), check=True
                )
            except Exception:
                pass

    def process_line(self, line):
        """Process a single line from script"""
        line = line.rstrip('\n')

        script_vars = getattr(self, 'script_vars', {})
        if script_vars:
            line = self._expand_variables(line, script_vars)

        # Skip empty lines and comments
        if not line or line.strip().startswith('#'):
            return True  # continue processing

        # Check for special commands in <>
        if line.startswith('<') and line.endswith('>'):
            cmd = line[1:-1].strip()
            cmd_lower = cmd.lower()

            # Clipboard:get
            if cmd_lower == 'clipboard:get':
                print("  [clipboard: get]")
                self._handle_clipboard_get()
                return True

            # Clipboard:set:text
            if cmd_lower.startswith('clipboard:set:'):
                text = cmd.split(':set:', 1)[1]
                print(f"  [clipboard: set]")
                self._handle_clipboard_set(text)
                return True

            # Wait command
            if cmd_lower.startswith('wait:'):
                try:
                    seconds = float(cmd.split(':', 1)[1])
                    print(f"  [waiting {seconds}s]")
                    time.sleep(seconds)
                except ValueError:
                    print(f"Warning: Invalid wait command '{cmd}'")
                return True

            # No-wait marker (processed later)
            elif cmd_lower == 'nowait':
                return False  # signal no Enter

            # Key combo or special key
            elif '+' in cmd:
                print(f"  [combo: {cmd}]")
                self.send_combo(cmd)
                return True

            # Single special key
            else:
                keycode, modifier = self._get_keycode(cmd)
                if keycode:
                    print(f"  [key: {cmd}]")
                    self.focus()
                    self.press_key(keycode, modifier)
                else:
                    print(f"Warning: Unknown key '{cmd}'")
                return True

        # Regular text - type it
        else:
            print(f"  > {line}")
            self.type_text(line)
            return None  # signal: check next line for nowait

    def run_script_file(self, script_path):
        """Execute commands from a script file"""
        print(f"\nExecuting script: {script_path}")

        if not self.window_valid:
            print("ERROR: No valid window found. Cannot execute script.")
            return False

        with open(script_path, 'r') as f:
            lines = f.readlines()

        se.execute_script(lines, self, vars_dict=self.script_vars)
        print("\nScript completed!")
        return True

    def run_commands(self, commands):
        """Execute commands from list"""
        print("\nExecuting commands...")

        if not self.window_valid:
            print("ERROR: No valid window found. Cannot execute commands.")
            return False

        lines = [c + '\n' if not c.endswith('\n') else c for c in commands]
        se.execute_script(lines, self, vars_dict=self.script_vars)
        print("\nCommands completed!")
        return True

    def wait_for_exit(self):
        """Wait for program to exit"""
        if self.launcher.process:
            print("\nWaiting for program to exit... (Ctrl+C to force quit)")
            try:
                self.launcher.wait_for_exit()
                print("Program exited.")
            except KeyboardInterrupt:
                print("\nForce quitting program...")
                self.launcher.cleanup()

    def cleanup(self):
        """Terminate the program"""
        self.launcher.cleanup()


def main():
    parser = argparse.ArgumentParser(
        description='Generic X11 Keypress Automation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Normal apps (default - works with most programs)
  %(prog)s "leafpad" text.txt -w leafpad
  %(prog)s "gedit" script.txt -w gedit
  %(prog)s "xterm" commands.txt -w xterm

  # Emulators (need --emulator-mode flag)
  %(prog)s "dosbox-x -c 'imgmount c c.img' -c 'boot c:'" dos.txt -w DOSBox --emulator-mode
  %(prog)s "vice" game.txt -w VICE --emulator-mode

  # Quick command
  %(prog)s "gedit" -c "Hello World" -c "<Ctrl+s>"

Script file format:
  dir /p              # Types 'dir /p' and presses Enter
  <F1>                # Presses F1 key
  <Ctrl+C>            # Presses Ctrl+C
  <F12+f>             # Presses F12 and f together
  <wait:2>            # Waits 2 seconds
  edit test.txt       # Types text
  <nowait>            # Previous line won't press Enter
  <Esc>               # Press Escape
  # This is a comment
        """
    )

    parser.add_argument('program', nargs='?', help='Program to launch (in quotes if has args)')
    parser.add_argument('script', nargs='?', help='Script file to execute')
    parser.add_argument('-c', '--command', action='append', help='Execute single command (can be repeated)')
    parser.add_argument('-d', '--delay', type=float, default=2.0, help='Startup delay in seconds (default: 2.0)')
    parser.add_argument('-t', '--typing-delay', type=float, default=0.03, help='Delay between keystrokes (default: 0.03)')
    parser.add_argument('-w', '--window', help='Window name pattern to search for (recommended)')
    parser.add_argument('-n', '--no-wait', action='store_true', help='Exit immediately after script (don\'t wait for program)')
    parser.add_argument('-e', '--emulator-mode', action='store_true', help='Use for emulators/VMs (DOSBox-X, VICE, etc.) that use US keyboard internally')
    parser.add_argument('--debug', action='store_true', help='Enable debug output for keyboard mapping')
    parser.add_argument('--list-windows', action='store_true', help='List all visible X11 windows and exit')
    parser.add_argument('--attach', type=int, help='Attach to already-running process by PID')
    parser.add_argument('--attach-window-id', help='Attach to existing window by ID (hex)')
    parser.add_argument('-a', '--arg', action='append', help='Set script variable NAME=VALUE (repeatable)')
    parser.add_argument('--compose-key', default='Alt_R', help='Key to use as compose key (default: Alt_R)')

    args = parser.parse_args()

    if args.list_windows:
        x11 = X11Display()
        finder = WindowFinder(x11)
        windows = finder.list_windows()
        for win in windows:
            print(f"0x{win['id']:08x}  {win['class'] or 'N/A':20}  PID={win['pid'] or 'N/A':6}  {win['name']}")
        x11.close()
        sys.exit(0)

    if not args.program and not args.attach and not args.attach_window_id:
        parser.error("Either program, --attach, or --attach-window-id is required")

    if not args.script and not args.command:
        parser.error("Either script file or -c command required")

    attach_pid = args.attach
    attach_window_id = args.attach_window_id

    auto = KeypressAutomation(
        args.program, args.delay, args.typing_delay, args.window,
        args.emulator_mode, args.debug,
        attach_pid=attach_pid, attach_window_id=attach_window_id,
        compose_key=args.compose_key,
    )

    if args.arg:
        for a in args.arg:
            if '=' in a:
                name, value = a.split('=', 1)
                auto.script_vars[name] = value

    try:
        if attach_pid or attach_window_id:
            if attach_window_id:
                wid = int(attach_window_id, 0)
                auto.window = auto.x11.display.create_resource_object('window', wid)
            elif args.window:
                auto.window = auto.finder.find(args.window, strategy='name')
            elif attach_pid:
                auto.window = auto.finder.find_by_pid(attach_pid)

            if auto.window:
                wid = hex(auto.window.id)
                try:
                    name = auto.window.get_wm_name() or "Unknown"
                except:
                    name = "Unknown"
                print(f"Found window: {wid} - {name}")
                auto.window_valid = True
            else:
                print("ERROR: Could not find target window!")
                return 1
        else:
            if not auto.start_program():
                print("\nFailed to find window. Exiting.")
                return 1

        if args.script:
            auto.run_script_file(args.script)
        elif args.command:
            auto.run_commands(args.command)

        if not args.no_wait:
            auto.wait_for_exit()
        else:
            print("\nScript done. Program still running.")

    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        if auto and hasattr(auto, 'launcher'):
            auto.launcher.cleanup()

    return 0


if __name__ == "__main__":
    sys.exit(main())
