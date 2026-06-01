"""
Core X11 automation primitives for keypress.

Provides reusable classes for X11 display management, window finding,
window control, and program launching.  All X11 connections are lazy
so the module can be imported without a running display (e.g. in headless CI).
"""

import argparse
import os
import shlex
import subprocess
import time
from signal import SIGTERM, SIGKILL

from Xlib import X, display, XK
from Xlib.ext.xtest import fake_input
from Xlib.protocol.event import ClientMessage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

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

KEYSYM_TO_CHAR = {
    0x0020: ' ', 0x0021: '!', 0x0022: '"', 0x0023: '#', 0x0024: '$',
    0x0025: '%', 0x0026: '&', 0x0027: "'", 0x0028: '(', 0x0029: ')',
    0x002a: '*', 0x002b: '+', 0x002c: ',', 0x002d: '-', 0x002e: '.',
    0x002f: '/', 0x003a: ':', 0x003b: ';', 0x003c: '<', 0x003d: '=',
    0x003e: '>', 0x003f: '?', 0x0040: '@', 0x005b: '[', 0x005c: '\\',
    0x005d: ']', 0x005e: '^', 0x005f: '_', 0x0060: '`', 0x007b: '{',
    0x007c: '|', 0x007d: '}', 0x007e: '~',
    0x0030: '0', 0x0031: '1', 0x0032: '2', 0x0033: '3', 0x0034: '4',
    0x0035: '5', 0x0036: '6', 0x0037: '7', 0x0038: '8', 0x0039: '9',
    0x0061: 'a', 0x0062: 'b', 0x0063: 'c', 0x0064: 'd', 0x0065: 'e',
    0x0066: 'f', 0x0067: 'g', 0x0068: 'h', 0x0069: 'i', 0x006a: 'j',
    0x006b: 'k', 0x006c: 'l', 0x006d: 'm', 0x006e: 'n', 0x006f: 'o',
    0x0070: 'p', 0x0071: 'q', 0x0072: 'r', 0x0073: 's', 0x0074: 't',
    0x0075: 'u', 0x0076: 'v', 0x0077: 'w', 0x0078: 'x', 0x0079: 'y',
    0x007a: 'z',
    0x0041: 'A', 0x0042: 'B', 0x0043: 'C', 0x0044: 'D', 0x0045: 'E',
    0x0046: 'F', 0x0047: 'G', 0x0048: 'H', 0x0049: 'I', 0x004a: 'J',
    0x004b: 'K', 0x004c: 'L', 0x004d: 'M', 0x004e: 'N', 0x004f: 'O',
    0x0050: 'P', 0x0051: 'Q', 0x0052: 'R', 0x0053: 'S', 0x0054: 'T',
    0x0055: 'U', 0x0056: 'V', 0x0057: 'W', 0x0058: 'X', 0x0059: 'Y',
    0x005a: 'Z',
}

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def get_full_property(window, atom_name, property_type=X.AnyPropertyType):
    """Read an X11 property from *window* by atom name.

    Returns the property value object, or ``None`` on any error.
    """
    try:
        atom = window.display.intern_atom(atom_name)
        return window.get_full_property(atom, property_type)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# X11Display
# ---------------------------------------------------------------------------

class X11Display:
    """Lazy X11 display connection.

    The :py:attr:`display` property creates the connection on first access,
    so importing this module never triggers an X11 roundtrip.
    """

    def __init__(self):
        self._display = None

    @property
    def display(self):
        if self._display is None:
            self._display = display.Display()
        return self._display

    def screen(self):
        return self.display.screen()

    def root(self):
        return self.screen().root

    def sync(self):
        self.display.sync()

    def close(self):
        if self._display is not None:
            try:
                self._display.close()
            except Exception:
                pass
            self._display = None

    def _get_keycode_range(self):
        """Return ``(min_keycode, max_keycode)`` from the display.

        Tries multiple attribute paths that exist across python-xlib
        versions, falling back to the standard X11 range ``(8, 255)``.
        """
        d = self.display
        for getter in (
            lambda: (d.min_keycode, d.max_keycode),
            lambda: (d.info.min_keycode, d.info.max_keycode),
            lambda: (d.display.info.min_keycode, d.display.info.max_keycode),
        ):
            try:
                return getter()
            except AttributeError:
                continue
        try:
            info = d._data
            if hasattr(info, 'min_keycode'):
                return info.min_keycode, info.max_keycode
        except Exception:
            pass
        return 8, 255


# ---------------------------------------------------------------------------
# WindowFinder
# ---------------------------------------------------------------------------

class WindowFinder:
    """Find X11 windows by class, role, name, or PID with built-in retry."""

    def __init__(self, x11_display, max_attempts=10, retry_sleep=0.5):
        self.xd = x11_display
        self.max_attempts = max_attempts
        self.retry_sleep = retry_sleep

    # -- public search methods ------------------------------------------------

    def find_by_class(self, name_pattern, root=None):
        """Find a window whose WM_CLASS res_class contains *name_pattern* (case-insensitive)."""
        root = root or self.xd.root()
        def _search():
            result = [None]
            self._walk_tree(root, lambda w: self._match_class(w, name_pattern, result))
            return result[0]
        return self._retry_search(_search)

    def find_by_role(self, name_pattern, root=None):
        """Find a window whose WM_WINDOW_ROLE contains *name_pattern* (case-insensitive)."""
        root = root or self.xd.root()
        def _search():
            result = [None]
            self._walk_tree(root, lambda w: self._match_role(w, name_pattern, result))
            return result[0]
        return self._retry_search(_search)

    def find_by_name(self, name_pattern, root=None):
        """Find a window whose WM_NAME / _NET_WM_NAME contains *name_pattern* (case-insensitive)."""
        root = root or self.xd.root()
        def _search():
            result = [None]
            self._walk_tree(root, lambda w: self._match_name(w, name_pattern, result))
            return result[0]
        return self._retry_search(_search)

    def find_by_pid(self, pid, root=None):
        """Find a window whose _NET_WM_PID equals *pid*."""
        root = root or self.xd.root()
        def _search():
            result = [None]
            self._walk_tree(root, lambda w: self._match_pid(w, pid, result))
            return result[0]
        return self._retry_search(_search)

    def list_windows(self, root=None):
        """Return a list of dicts ``{id, class, role, name, pid}`` for all named windows."""
        root = root or self.xd.root()
        windows = []
        self._walk_tree(root, lambda w: self._collect_window(w, windows))
        return windows

    def find(self, identifier, strategy='class', root=None):
        """Try multiple search strategies in order until a window is found.

        *strategy* is one of ``class``, ``role``, ``name``, ``pid`` or
        ``all`` (tries class -> role -> name).

        Raises :class:`RuntimeError` if no window is found after all retries.
        """
        strategies = {
            'class': lambda: self.find_by_class(identifier, root),
            'role': lambda: self.find_by_role(identifier, root),
            'name': lambda: self.find_by_name(identifier, root),
            'pid': lambda: self.find_by_pid(int(identifier), root),
        }
        order = ['class', 'role', 'name'] if strategy == 'all' else [strategy]
        for s in order:
            win = strategies[s]()
            if win is not None:
                return win
        raise RuntimeError(f"Window not found: identifier={identifier!r} strategy={strategy}")

    # -- match helpers --------------------------------------------------------

    def _match_class(self, window, pattern, result):
        if result[0] is not None:
            return
        cls = self._get_wm_class(window)
        if cls and pattern.lower() in cls.lower():
            result[0] = window

    def _match_role(self, window, pattern, result):
        if result[0] is not None:
            return
        role = self._get_wm_role(window)
        if role and pattern.lower() in role.lower():
            result[0] = window

    def _match_name(self, window, pattern, result):
        if result[0] is not None:
            return
        name = self._get_wm_name(window)
        if name and pattern.lower() in name.lower():
            result[0] = window

    def _match_pid(self, window, pid, result):
        if result[0] is not None:
            return
        wpid = self._get_wm_pid(window)
        if wpid is not None and wpid == pid:
            name = self._get_wm_name(window)
            if name:
                result[0] = window

    def _collect_window(self, window, out):
        name = self._get_wm_name(window)
        if not name:
            return
        out.append({
            'id': window.id,
            'class': self._get_wm_class(window) or '',
            'role': self._get_wm_role(window) or '',
            'name': name,
            'pid': self._get_wm_pid(window),
        })

    # -- property readers -----------------------------------------------------

    def _get_wm_name(self, window):
        """Get WM_NAME with _NET_WM_NAME UTF-8 fallback."""
        try:
            name = window.get_wm_name()
            if name:
                return name
        except Exception:
            pass
        prop = get_full_property(window, '_NET_WM_NAME')
        if prop and prop.value:
            try:
                return prop.value.decode('utf-8') if isinstance(prop.value, bytes) else str(prop.value)
            except Exception:
                pass
        return None

    def _get_wm_class(self, window):
        """Get WM_CLASS res_class (second element)."""
        try:
            cls = window.get_wm_class()
            if cls and len(cls) >= 2:
                return cls[1]
        except Exception:
            pass
        return None

    def _get_wm_role(self, window):
        """Get WM_WINDOW_ROLE property."""
        try:
            role = window.get_wm_window_role()
            if role:
                return role[0] if isinstance(role, (list, tuple)) else str(role)
        except Exception:
            pass
        return None

    def _get_wm_pid(self, window):
        """Get _NET_WM_PID property as int, or None."""
        prop = get_full_property(window, '_NET_WM_PID')
        if prop and prop.value:
            try:
                return int(prop.value[0])
            except (IndexError, TypeError, ValueError):
                pass
        return None

    # -- tree walkers ---------------------------------------------------------

    def _walk_tree(self, window, visitor):
        """Walk the window tree depth-first, calling *visitor* on each."""
        try:
            visitor(window)
        except Exception:
            pass
        try:
            for child in window.query_tree().children:
                self._walk_tree(child, visitor)
        except Exception:
            pass

    def _walk_all(self, window, out):
        """Collect every window into *out* (flat list)."""
        try:
            out.append(window)
        except Exception:
            pass
        try:
            for child in window.query_tree().children:
                self._walk_all(child, out)
        except Exception:
            pass

    # -- retry wrapper --------------------------------------------------------

    def _retry_search(self, search_fn):
        for attempt in range(self.max_attempts):
            result = search_fn()
            if result is not None:
                return result
            time.sleep(self.retry_sleep)
        return None


# ---------------------------------------------------------------------------
# WindowController
# ---------------------------------------------------------------------------

class WindowController:
    """Control X11 windows — focus, raise, and validate."""

    def __init__(self, x11_display):
        self.xd = x11_display

    def is_valid(self, window):
        """Return True if *window* is still alive (get_attributes succeeds)."""
        try:
            window.get_attributes()
            return True
        except Exception:
            return False

    def focus(self, window, max_retries=3):
        """Aggressively focus *window* using X setInputFocus, configure, and EWMH _NET_ACTIVE_WINDOW.

        Uses exponential backoff between retries (``0.05 * 2**attempt``).

        Returns True if focus was verified, False after exhausting retries.
        """
        for attempt in range(max_retries):
            try:
                window.set_input_focus(X.RevertToParent, X.CurrentTime)
                window.configure(stack_mode=X.Above)

                root = self.xd.root()
                net_active = self.xd.display.intern_atom('_NET_ACTIVE_WINDOW')
                wm_protocols = self.xd.display.intern_atom('WM_PROTOCOLS')
                event = ClientMessage(
                    window=window,
                    client_type=wm_protocols,
                    data=(32, [net_active, X.CurrentTime, 0, 0, 0]),
                )
                event.type = X.ClientMessage
                root.send_event(
                    event,
                    event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask,
                )

                self.xd.sync()

                if self._verify_focus(window):
                    return True
            except Exception:
                pass
            time.sleep(0.05 * (2 ** attempt))
        return False

    def _verify_focus(self, window):
        """Check whether *window* currently has input focus."""
        try:
            focused = self.xd.display.get_input_focus()
            if focused and focused.focus == window:
                return True
        except Exception:
            pass
        return False


# ---------------------------------------------------------------------------
# ProgramLauncher
# ---------------------------------------------------------------------------

class ProgramLauncher:
    """Launch an external program and manage its lifetime."""

    def __init__(self):
        self.process = None
        self.pid = None

    def launch(self, cmd_string):
        """Run *cmd_string* via :func:`shlex.split` in a new session.

        Returns the PID of the child process.
        """
        args = shlex.split(cmd_string)
        self.process = subprocess.Popen(args, preexec_fn=os.setsid)
        self.pid = self.process.pid
        return self.pid

    def cleanup(self):
        """Terminate the child process (SIGTERM, then SIGKILL after 3 s)."""
        if self.process is None:
            return
        try:
            os.killpg(self.pid, SIGTERM)
        except ProcessLookupError:
            pass
        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(self.pid, SIGKILL)
            except ProcessLookupError:
                pass
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
        self.process = None
        self.pid = None

    def wait_for_exit(self):
        """Block until the child exits.  On :exc:`KeyboardInterrupt`, calls :meth:`cleanup` and re-raises."""
        if self.process is None:
            return
        try:
            self.process.wait()
        except KeyboardInterrupt:
            self.cleanup()
            raise


# ---------------------------------------------------------------------------
# CLI argument helpers
# ---------------------------------------------------------------------------

def add_window_args(parser):
    """Add window-selection arguments to *parser*."""
    parser.add_argument('-w', '--window', help='Window name pattern to search for')
    parser.add_argument('--window-strategy', default='class',
                        choices=['class', 'role', 'name', 'pid', 'all'],
                        help='Window search strategy (default: class)')
    parser.add_argument('--max-attempts', type=int, default=10,
                        help='Max retries when searching for a window (default: 10)')


def add_delay_args(parser):
    """Add timing-delay arguments to *parser*."""
    parser.add_argument('-d', '--delay', type=float, default=2.0,
                        help='Startup delay in seconds (default: 2.0)')
    parser.add_argument('-t', '--typing-delay', type=float, default=0.03,
                        help='Delay between keystrokes (default: 0.03)')


def add_debug_args(parser):
    """Add debug flag to *parser*."""
    parser.add_argument('--debug', action='store_true', help='Enable debug output')


def add_attach_args(parser):
    """Add attach-mode arguments to *parser*.

    * ``--attach`` takes a PID integer.
    * ``--attach-window-id`` accepts a hex or decimal X11 window ID.
    """
    parser.add_argument('--attach', type=int,
                        help='Attach to already-running process by PID')
    parser.add_argument('--attach-window-id', type=lambda v: int(v, 0),
                        help='Attach to existing window by ID (hex or decimal)')


def add_list_windows_flag(parser):
    """Add --list-windows flag to *parser*."""
    parser.add_argument('--list-windows', action='store_true',
                        help='List all visible X11 windows and exit')