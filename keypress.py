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
from Xlib import X, display, XK
from Xlib.ext.xtest import fake_input

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
    # Manual keysym to character mapping for common symbols
    # XK.keysym_to_string() doesn't work reliably for all keysyms
    KEYSYM_TO_CHAR = {
        # Basic ASCII printable characters
        0x0020: ' ', 0x0021: '!', 0x0022: '"', 0x0023: '#', 0x0024: '$',
        0x0025: '%', 0x0026: '&', 0x0027: "'", 0x0028: '(', 0x0029: ')',
        0x002a: '*', 0x002b: '+', 0x002c: ',', 0x002d: '-', 0x002e: '.',
        0x002f: '/', 0x003a: ':', 0x003b: ';', 0x003c: '<', 0x003d: '=',
        0x003e: '>', 0x003f: '?', 0x0040: '@', 0x005b: '[', 0x005c: '\\',
        0x005d: ']', 0x005e: '^', 0x005f: '_', 0x0060: '`', 0x007b: '{',
        0x007c: '|', 0x007d: '}', 0x007e: '~',
        # Numbers
        0x0030: '0', 0x0031: '1', 0x0032: '2', 0x0033: '3', 0x0034: '4',
        0x0035: '5', 0x0036: '6', 0x0037: '7', 0x0038: '8', 0x0039: '9',
        # Lowercase letters
        0x0061: 'a', 0x0062: 'b', 0x0063: 'c', 0x0064: 'd', 0x0065: 'e',
        0x0066: 'f', 0x0067: 'g', 0x0068: 'h', 0x0069: 'i', 0x006a: 'j',
        0x006b: 'k', 0x006c: 'l', 0x006d: 'm', 0x006e: 'n', 0x006f: 'o',
        0x0070: 'p', 0x0071: 'q', 0x0072: 'r', 0x0073: 's', 0x0074: 't',
        0x0075: 'u', 0x0076: 'v', 0x0077: 'w', 0x0078: 'x', 0x0079: 'y',
        0x007a: 'z',
        # Uppercase letters
        0x0041: 'A', 0x0042: 'B', 0x0043: 'C', 0x0044: 'D', 0x0045: 'E',
        0x0046: 'F', 0x0047: 'G', 0x0048: 'H', 0x0049: 'I', 0x004a: 'J',
        0x004b: 'K', 0x004c: 'L', 0x004d: 'M', 0x004e: 'N', 0x004f: 'O',
        0x0050: 'P', 0x0051: 'Q', 0x0052: 'R', 0x0053: 'S', 0x0054: 'T',
        0x0055: 'U', 0x0056: 'V', 0x0057: 'W', 0x0058: 'X', 0x0059: 'Y',
        0x005a: 'Z',
    }
    
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
    
    # Special key name to keycode mapping
    SPECIAL_KEYS = {
        'return': 36, 'enter': 36,
        'escape': 9, 'esc': 9,
        'tab': 23,
        'backspace': 22, 'bksp': 22,
        'delete': 119, 'del': 119,
        'space': 65,
        'f1': 67, 'f2': 68, 'f3': 69, 'f4': 70,
        'f5': 71, 'f6': 72, 'f7': 73, 'f8': 74,
        'f9': 75, 'f10': 76, 'f11': 95, 'f12': 96,
        'up': 111, 'down': 116, 'left': 113, 'right': 114,
        'home': 110, 'end': 115,
        'pageup': 112, 'pagedown': 117, 'pgup': 112, 'pgdn': 117,
        'insert': 118, 'ins': 118,
        'shift': 50, 'ctrl': 37, 'control': 37,
        'alt': 64, 'meta': 64, 'altgr': 108, 'iso_level3_shift': 108,
        'super': 133, 'win': 133,
    }
    
    def __init__(self, program_cmd, startup_delay=2.0, typing_delay=0.03, window_name=None, emulator_mode=False, debug=False):
        self.program_cmd = program_cmd
        self.startup_delay = startup_delay
        self.typing_delay = typing_delay
        self.window_name = window_name
        self.emulator_mode = emulator_mode
        self.debug = debug
        self.display = display.Display()
        self.process = None
        self.window = None
        self.window_valid = False
        self.keymap_cache = {}  # Cache for system layout lookups
        
        if emulator_mode:
            print("Mode: Emulator (US layout for DOSBox-X, VICE, etc.)")
        else:
            print("Mode: Normal (respects your system keyboard layout)")
            self._build_keymap_cache()
        
    def _get_keycode_range(self):
        """Try multiple methods to get min/max keycode from display"""
        # Method 1: Try direct attributes (some versions)
        try:
            return self.display.min_keycode, self.display.max_keycode
        except AttributeError:
            pass
        
        # Method 2: Try info attribute
        try:
            return self.display.info.min_keycode, self.display.info.max_keycode
        except AttributeError:
            pass
        
        # Method 3: Try display.display.info
        try:
            return self.display.display.info.min_keycode, self.display.display.info.max_keycode
        except AttributeError:
            pass
        
        # Method 4: Check for _data or connection info
        try:
            info = self.display._data
            if hasattr(info, 'min_keycode'):
                return info.min_keycode, info.max_keycode
        except:
            pass
        
        # Fallback: Use standard X11 keycode range
        print("Warning: Could not auto-detect keycode range, using standard X11 range (8-255)")
        return 8, 255
    
    def _keysym_to_char(self, keysym):
        """Convert keysym to character, using manual mapping if needed"""
        # First try our manual mapping
        if keysym in self.KEYSYM_TO_CHAR:
            return self.KEYSYM_TO_CHAR[keysym]
        
        # Fall back to XK.keysym_to_string
        char = XK.keysym_to_string(keysym)
        if char and len(char) == 1:
            return char
        
        return None
    
    def _build_keymap_cache(self):
        """Build a cache of character -> (keycode, modifiers) from actual keyboard layout"""
        print("Building keyboard map from system layout...")
        
        # Get min/max keycode
        min_keycode, max_keycode = self._get_keycode_range()
        print(f"Keycode range: {min_keycode}-{max_keycode}")
        
        # Get the keyboard mapping from X11
        try:
            keymap = self.display.get_keyboard_mapping(min_keycode, max_keycode - min_keycode + 1)
        except Exception as e:
            print(f"Warning: Could not get keyboard mapping: {e}")
            print("Falling back to emulator mode behavior")
            self.keymap_cache = {}
            return
        
        # Debug: let's see what keysyms exist for bracket-like keys
        if self.debug:
            print("\n=== DEBUG: Scanning for bracket/backslash keysyms ===")
        
        # Build reverse mapping: character -> (keycode, modifiers)
        # modifiers: 0=none, 1=shift, 2=altgr, 3=shift+altgr
        for keycode in range(min_keycode, max_keycode + 1):
            index = keycode - min_keycode
            if index >= len(keymap):
                continue
                
            keysyms = keymap[index]
            if not keysyms:
                continue
            
            # Debug output
            if self.debug:
                for col_idx, keysym in enumerate(keysyms):
                    if keysym != 0:
                        char = self._keysym_to_char(keysym)
                        # Show if it's a bracket/backslash or other special char
                        if keysym in [0x5b, 0x5d, 0x5c, 0x7b, 0x7d, 0x7c]:  # [] \ {} |
                            print(f"  Keycode {keycode}, col {col_idx}: keysym={hex(keysym)}, char='{char}'")
            
            # Check ALL columns (Finnish layout uses column 4 for AltGr!)
            for col in range(len(keysyms)):
                keysym = keysyms[col]
                if keysym == 0:
                    continue
                
                # Try to convert keysym to character using our improved method
                char = self._keysym_to_char(keysym)
                if char:
                    # Only cache if not already present (prefer simpler modifiers)
                    if char not in self.keymap_cache:
                        # Map column to modifier
                        # X11 keymap columns vary by layout:
                        # Standard: 0=none, 1=shift, 2=altgr, 3=shift+altgr
                        # Finnish:  0=none, 1=shift, 2=none, 3=shift, 4=altgr, 5=shift+altgr
                        if col == 0:
                            modifier = 0
                        elif col == 1:
                            modifier = 1
                        elif col in (2, 4):  # AltGr can be in col 2 or 4
                            modifier = 2
                        elif col in (3, 5):  # Shift+AltGr
                            modifier = 3
                        else:
                            # Higher columns - assume AltGr
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
        self.process = subprocess.Popen(self.program_cmd, shell=True)
        
        print(f"Process PID: {self.process.pid}")
        print(f"Waiting {self.startup_delay}s for program window...")
        time.sleep(self.startup_delay)
        
        # Find the window
        if self.window_name:
            self.window = self._find_window_by_name(self.window_name)
        else:
            self.window = self._find_window_by_pid(self.process.pid)
        
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
    
    def _find_window_by_pid(self, pid, max_attempts=10):
        """Find window by process PID"""
        print(f"Searching for window of PID {pid}...")
        
        for attempt in range(max_attempts):
            root = self.display.screen().root
            window = self._search_by_pid(root, pid)
            if window:
                return window
            time.sleep(0.5)
        
        return None
    
    def _search_by_pid(self, window, target_pid):
        """Recursively search for window by PID"""
        try:
            # Get window PID
            atom = self.display.intern_atom('_NET_WM_PID')
            pid_property = window.get_full_property(atom, X.AnyPropertyType)
            
            if pid_property and pid_property.value:
                window_pid = pid_property.value[0]
                if window_pid == target_pid:
                    # Make sure it's a real window with a name
                    name = window.get_wm_name()
                    if name:
                        return window
            
            # Search children
            children = window.query_tree().children
            for child in children:
                result = self._search_by_pid(child, target_pid)
                if result:
                    return result
        except:
            pass
        
        return None
    
    def _find_window_by_name(self, name_pattern, max_attempts=10):
        """Find window by name pattern"""
        print(f"Searching for window matching '{name_pattern}'...")
        
        for attempt in range(max_attempts):
            root = self.display.screen().root
            window = self._search_window_tree(root, name_pattern)
            if window:
                return window
            time.sleep(0.5)
        
        return None
    
    def _search_window_tree(self, window, name_pattern):
        """Recursively search for window by name"""
        try:
            win_name = window.get_wm_name()
            if win_name and name_pattern.lower() in win_name.lower():
                return window
            
            children = window.query_tree().children
            for child in children:
                result = self._search_window_tree(child, name_pattern)
                if result:
                    return result
        except:
            pass
        return None
    
    def _check_window_valid(self):
        """Check if window is still valid"""
        if not self.window:
            return False
        
        try:
            # Try to get window attributes
            self.window.get_attributes()
            return True
        except:
            self.window_valid = False
            return False
    
    def focus(self):
        """Focus the target window"""
        if not self.window or not self._check_window_valid():
            return False
        
        try:
            self.window.set_input_focus(X.RevertToParent, X.CurrentTime)
            self.window.configure(stack_mode=X.Above)
            self.display.sync()
            time.sleep(0.05)
            return True
        except Exception as e:
            print(f"Warning: Could not focus window: {e}")
            self.window_valid = False
            return False
    
    def _get_keycode_us(self, key_name):
        """Convert key name to keycode using US layout - returns (keycode, modifier)"""
        key_lower = key_name.lower()
        
        # Check special keys first
        if key_lower in self.SPECIAL_KEYS:
            return (self.SPECIAL_KEYS[key_lower], 0)
        
        # Check US keymap for single characters
        if len(key_name) == 1 and key_name in self.US_KEYMAP:
            keycode, needs_shift = self.US_KEYMAP[key_name]
            return (keycode, 1 if needs_shift else 0)
        
        return (None, 0)
    
    def _get_keycode_system(self, key_name):
        """Convert key name to keycode using system layout - returns (keycode, modifier)"""
        key_lower = key_name.lower()
        
        # Check special keys first
        if key_lower in self.SPECIAL_KEYS:
            return (self.SPECIAL_KEYS[key_lower], 0)
        
        # For single characters, look up in our keymap cache
        if len(key_name) == 1:
            if key_name in self.keymap_cache:
                return self.keymap_cache[key_name]
            else:
                # Not in cache - character not available in current layout
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
        if not self._check_window_valid():
            return False
        
        try:
            # Press modifiers
            if modifier in (1, 3):  # Shift or Shift+AltGr
                fake_input(self.display, X.KeyPress, 50)  # Shift
            if modifier in (2, 3):  # AltGr or Shift+AltGr
                fake_input(self.display, X.KeyPress, 108)  # AltGr (ISO_Level3_Shift)
            
            # Press the key
            fake_input(self.display, X.KeyPress, keycode)
            self.display.sync()
            time.sleep(0.02)
            fake_input(self.display, X.KeyRelease, keycode)
            self.display.sync()
            
            # Release modifiers in reverse order
            if modifier in (2, 3):  # AltGr or Shift+AltGr
                fake_input(self.display, X.KeyRelease, 108)
            if modifier in (1, 3):  # Shift or Shift+AltGr
                fake_input(self.display, X.KeyRelease, 50)
            
            time.sleep(0.02)
            return True
        except Exception as e:
            print(f"Warning: Key press failed: {e}")
            return False
    
    def send_combo(self, combo_str):
        """Send key combination like 'Ctrl+Alt+Del' or 'F12+f'"""
        if not self.focus():
            return False
        
        # Parse the combination
        keys = [k.strip() for k in combo_str.split('+')]
        key_info = []
        
        for key in keys:
            keycode, modifier = self._get_keycode(key)
            if keycode:
                # For combos, we press the key itself without modifiers
                key_info.append(keycode)
            else:
                print(f"Warning: Unknown key '{key}' in combo '{combo_str}'")
                return False
        
        try:
            # Press all keys in order
            for keycode in key_info:
                fake_input(self.display, X.KeyPress, keycode)
                self.display.sync()
                time.sleep(0.02)
            
            # Release in reverse order
            for keycode in reversed(key_info):
                fake_input(self.display, X.KeyRelease, keycode)
                self.display.sync()
                time.sleep(0.02)
            return True
        except Exception as e:
            print(f"Warning: Combo failed: {e}")
            return False
    
    def type_text(self, text):
        """Type a string of text"""
        if not self.focus():
            return False
        
        for char in text:
            keycode, modifier = self._get_keycode(char)
            
            if not keycode:
                print(f"Warning: Cannot type character '{char}' (not in current layout, skipping)")
                continue
            
            try:
                self.press_key(keycode, modifier)
                time.sleep(self.typing_delay)
            except Exception as e:
                print(f"Warning: Failed to type '{char}': {e}")
                continue
        
        return True
    
    def process_line(self, line):
        """Process a single line from script"""
        line = line.rstrip('\n')
        
        # Skip empty lines and comments
        if not line or line.strip().startswith('#'):
            return True  # continue processing
        
        # Check for special commands in <>
        if line.startswith('<') and line.endswith('>'):
            cmd = line[1:-1].strip()
            
            # Wait command
            if cmd.lower().startswith('wait:'):
                try:
                    seconds = float(cmd.split(':', 1)[1])
                    print(f"  [waiting {seconds}s]")
                    time.sleep(seconds)
                except ValueError:
                    print(f"Warning: Invalid wait command '{cmd}'")
                return True
            
            # No-wait marker (processed later)
            elif cmd.lower() == 'nowait':
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
            raw_lines = f.readlines()

        lines = expand_script_loops(raw_lines)

        i = 0
        while i < len(lines):
            line = lines[i]
            
            # Process the line
            result = self.process_line(line)
            
            # Check if we should press Enter
            if result is None:  # was regular text
                # Check if next line is <nowait>
                if i + 1 < len(lines) and lines[i + 1].strip() == '<nowait>':
                    i += 1  # skip the nowait marker
                else:
                    # Press Enter after typing
                    if self.focus():
                        self.press_key(self.SPECIAL_KEYS['return'])
            
            i += 1
        
        print("\nScript completed!")
        return True
    
    def run_commands(self, commands):
        """Execute commands from list"""
        print("\nExecuting commands...")
        
        if not self.window_valid:
            print("ERROR: No valid window found. Cannot execute commands.")
            return False
        
        for cmd in commands:
            result = self.process_line(cmd)
            if result is None:  # was text
                if self.focus():
                    self.press_key(self.SPECIAL_KEYS['return'])
        
        print("\nCommands completed!")
        return True
    
    def wait_for_exit(self):
        """Wait for child process to exit"""
        if self.process:
            print("\nWaiting for program to exit... (Ctrl+C to force quit)")
            try:
                self.process.wait()
                print("Program exited.")
            except KeyboardInterrupt:
                print("\nForce quitting program...")
                self.process.terminate()
                try:
                    self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    print("Killing program...")
                    self.process.kill()
                    self.process.wait()
    
    def cleanup(self):
        """Terminate the program"""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()


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
    
    parser.add_argument('program', help='Program to launch (in quotes if has args)')
    parser.add_argument('script', nargs='?', help='Script file to execute')
    parser.add_argument('-c', '--command', action='append', help='Execute single command (can be repeated)')
    parser.add_argument('-d', '--delay', type=float, default=2.0, help='Startup delay in seconds (default: 2.0)')
    parser.add_argument('-t', '--typing-delay', type=float, default=0.03, help='Delay between keystrokes (default: 0.03)')
    parser.add_argument('-w', '--window', help='Window name pattern to search for (recommended)')
    parser.add_argument('-n', '--no-wait', action='store_true', help='Exit immediately after script (don\'t wait for program)')
    parser.add_argument('-e', '--emulator-mode', action='store_true', help='Use for emulators/VMs (DOSBox-X, VICE, etc.) that use US keyboard internally')
    parser.add_argument('--debug', action='store_true', help='Enable debug output for keyboard mapping')
    
    args = parser.parse_args()
    
    # Validate input
    if not args.script and not args.command:
        parser.error("Either script file or -c command required")
    
    # Create automation instance
    auto = KeypressAutomation(args.program, args.delay, args.typing_delay, args.window, args.emulator_mode, args.debug)
    
    try:
        # Start program
        if not auto.start_program():
            print("\nFailed to find window. Exiting.")
            return 1
        
        # Execute commands
        if args.script:
            auto.run_script_file(args.script)
        elif args.command:
            auto.run_commands(args.command)
        
        # Wait for program to exit (default behavior)
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
    
    return 0


if __name__ == "__main__":
    sys.exit(main())