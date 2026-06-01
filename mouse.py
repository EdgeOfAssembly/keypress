#!/usr/bin/env python3
"""
X11 Mouse Automation Script

Usage:
    ./mouse.py "program --args" script.txt
    ./mouse.py "program" -c "<click:100,200>" -c "<wait:1>"
    ./mouse.py --attach leafpad -c "<click:100,200>"
"""

import argparse
import sys
import time

from Xlib import X
from Xlib.ext.xtest import fake_input

from kp_core import (
    X11Display,
    WindowFinder,
    WindowController,
    ProgramLauncher,
    add_window_args,
    add_delay_args,
    add_debug_args,
    add_attach_args,
    add_list_windows_flag,
)


class MouseAutomation:
    """Mouse automation for X11 using XTest extension."""

    def __init__(self, program_cmd, startup_delay=2.0, event_delay=0.03,
                 window_name=None, debug=False,
                 attach_pid=None, attach_window_id=None):
        self.program_cmd = program_cmd
        self.startup_delay = startup_delay
        self.event_delay = event_delay
        self.window_name = window_name
        self.debug = debug
        self.attach_pid = attach_pid
        self.attach_window_id = attach_window_id

        self.x11 = X11Display()
        self.finder = WindowFinder(self.x11)
        self.controller = WindowController(self.x11)
        self.launcher = ProgramLauncher()

        self.window = None
        self.window_valid = False

    def start_program(self):
        """Launch the target program and find its window."""
        if self.program_cmd:
            print(f"Starting: {self.program_cmd}")
            pid = self.launcher.launch(self.program_cmd)
            print(f"Process PID: {pid}")
            print(f"Waiting {self.startup_delay}s for program window...")
            time.sleep(self.startup_delay)

            if self.window_name:
                self.window = self.finder.find(self.window_name, strategy='name')
            else:
                self.window = self.finder.find_by_pid(pid)

            if self.window:
                wid = hex(self.window.id)
                try:
                    name = self.window.get_wm_name() or "Unknown"
                except Exception:
                    name = "Unknown"
                print(f"Found window: {wid} - {name}")
                self.window_valid = True
                time.sleep(0.5)
                return True
            else:
                print("WARNING: Could not find program window!")
                print("Mouse commands may not work. Try:")
                print(f"  1. Increase delay: -d 5")
                print(f"  2. Specify window name: -w 'window_name'")
                return False
        return True

    def _ensure_window_focused(self):
        """Ensure the target window is focused and valid."""
        if not self.window or not self.controller.is_valid(self.window):
            self.window_valid = False
            return False
        if not self.controller.focus(self.window):
            return False
        return True

    def move(self, x, y):
        """Move cursor to screen coordinates (x, y)."""
        try:
            root = self.x11.screen().root
            root.warp_pointer(x, y, 0, 0, 0, 0)
            self.x11.sync()
            time.sleep(self.event_delay)
            if self.debug:
                print(f"  [moved to {x},{y}]")
        except Exception as e:
            print(f"Warning: Move failed: {e}")

    def click(self, x, y, button=1):
        """Move to (x, y) and perform a mouse click with the specified button."""
        try:
            self.move(x, y)
            fake_input(self.x11.display, X.ButtonPress, button)
            self.x11.sync()
            time.sleep(self.event_delay)
            fake_input(self.x11.display, X.ButtonRelease, button)
            self.x11.sync()
            time.sleep(self.event_delay)
            if self.debug:
                print(f"  [clicked button {button} at {x},{y}]")
        except Exception as e:
            print(f"Warning: Click failed: {e}")

    def right_click(self, x, y):
        """Move to (x, y) and perform a right click (button 3)."""
        self.click(x, y, button=3)

    def double_click(self, x, y):
        """Move to (x, y) and perform a double click (two rapid button 1 clicks)."""
        try:
            self.move(x, y)
            for _ in range(2):
                fake_input(self.x11.display, X.ButtonPress, 1)
                self.x11.sync()
                time.sleep(self.event_delay)
                fake_input(self.x11.display, X.ButtonRelease, 1)
                self.x11.sync()
                time.sleep(self.event_delay)
            if self.debug:
                print(f"  [double-clicked at {x},{y}]")
        except Exception as e:
            print(f"Warning: Double click failed: {e}")

    def drag(self, x1, y1, x2, y2):
        """Drag from (x1, y1) to (x2, y2) with button 1 pressed."""
        try:
            self.move(x1, y1)
            fake_input(self.x11.display, X.ButtonPress, 1)
            self.x11.sync()
            time.sleep(self.event_delay)
            self.move(x2, y2)
            fake_input(self.x11.display, X.ButtonRelease, 1)
            self.x11.sync()
            time.sleep(self.event_delay)
            if self.debug:
                print(f"  [dragged from {x1},{y1} to {x2},{y2}]")
        except Exception as e:
            print(f"Warning: Drag failed: {e}")

    def scroll(self, direction, amount=1):
        """Scroll in the specified direction ('up' or 'down') by amount clicks."""
        button = 4 if direction == 'up' else 5
        try:
            for _ in range(amount):
                fake_input(self.x11.display, X.ButtonPress, button)
                self.x11.sync()
                time.sleep(self.event_delay)
                fake_input(self.x11.display, X.ButtonRelease, button)
                self.x11.sync()
                time.sleep(self.event_delay)
            if self.debug:
                print(f"  [scrolled {direction} {amount} times]")
        except Exception as e:
            print(f"Warning: Scroll failed: {e}")

    def process_line(self, line):
        """Process a single line from a mouse script."""
        line = line.rstrip('\n')

        if not line or line.strip().startswith('#'):
            return True

        if line.startswith('<') and line.endswith('>'):
            cmd = line[1:-1].strip()
            parts = cmd.lower().split(':')

            if parts[0] == 'click':
                if len(parts) >= 2:
                    coords = parts[1].split(',')
                    if len(coords) == 2:
                        x, y = int(coords[0]), int(coords[1])
                        print(f"  [click: {x},{y}]")
                        self.click(x, y)
                    else:
                        print(f"Warning: Invalid click coordinates '{parts[1]}'")
                return True

            elif parts[0] == 'rightclick':
                if len(parts) >= 2:
                    coords = parts[1].split(',')
                    if len(coords) == 2:
                        x, y = int(coords[0]), int(coords[1])
                        print(f"  [rightclick: {x},{y}]")
                        self.right_click(x, y)
                    else:
                        print(f"Warning: Invalid rightclick coordinates '{parts[1]}'")
                return True

            elif parts[0] == 'dblclick':
                if len(parts) >= 2:
                    coords = parts[1].split(',')
                    if len(coords) == 2:
                        x, y = int(coords[0]), int(coords[1])
                        print(f"  [dblclick: {x},{y}]")
                        self.double_click(x, y)
                    else:
                        print(f"Warning: Invalid dblclick coordinates '{parts[1]}'")
                return True

            elif parts[0] == 'move':
                if len(parts) >= 2:
                    coords = parts[1].split(',')
                    if len(coords) == 2:
                        x, y = int(coords[0]), int(coords[1])
                        print(f"  [move: {x},{y}]")
                        self.move(x, y)
                    else:
                        print(f"Warning: Invalid move coordinates '{parts[1]}'")
                return True

            elif parts[0] == 'drag':
                if len(parts) >= 3:
                    coords1 = parts[1].split(',')
                    coords2 = parts[2].split(',')
                    if len(coords1) == 2 and len(coords2) == 2:
                        x1, y1 = int(coords1[0]), int(coords1[1])
                        x2, y2 = int(coords2[0]), int(coords2[1])
                        print(f"  [drag: {x1},{y1} -> {x2},{y2}]")
                        self.drag(x1, y1, x2, y2)
                    else:
                        print(f"Warning: Invalid drag coordinates")
                return True

            elif parts[0] == 'scroll':
                if len(parts) >= 3:
                    direction = parts[1]
                    try:
                        amount = int(parts[2])
                        print(f"  [scroll: {direction} x{amount}]")
                        self.scroll(direction, amount)
                    except ValueError:
                        print(f"Warning: Invalid scroll amount '{parts[2]}'")
                elif len(parts) == 2:
                    direction = parts[1]
                    print(f"  [scroll: {direction}]")
                    self.scroll(direction)
                return True

            elif parts[0] == 'wait':
                if len(parts) >= 2:
                    try:
                        seconds = float(parts[1])
                        print(f"  [waiting {seconds}s]")
                        time.sleep(seconds)
                    except ValueError:
                        print(f"Warning: Invalid wait time '{parts[1]}'")
                return True

            else:
                print(f"Warning: Unknown command '{cmd}'")
                return True

        return True

    def run_script_file(self, path):
        """Read and execute a mouse script file."""
        print(f"\nExecuting script: {path}")

        if not self.window_valid and self.window_name:
            if not self._ensure_window_focused():
                print("ERROR: No valid window found. Cannot execute script.")
                return False

        try:
            with open(path, 'r') as f:
                lines = f.readlines()
        except FileNotFoundError:
            print(f"Error: Script file not found: {path}")
            return False
        except Exception as e:
            print(f"Error reading script: {e}")
            return False

        for line in lines:
            self.process_line(line)

        print("\nScript completed!")
        return True

    def run_commands(self, commands):
        """Execute a list of mouse commands."""
        print("\nExecuting commands...")

        if not self.window_valid and self.window_name:
            if not self._ensure_window_focused():
                print("ERROR: No valid window found. Cannot execute commands.")
                return False

        for cmd in commands:
            self.process_line(cmd)

        print("\nCommands completed!")
        return True

    def wait_for_exit(self):
        """Wait for the launched program to exit."""
        if self.launcher.process:
            print("\nWaiting for program to exit... (Ctrl+C to force quit)")
            try:
                self.launcher.wait_for_exit()
                print("Program exited.")
            except KeyboardInterrupt:
                print("\nForce quitting program...")
                self.launcher.cleanup()
                raise

    def cleanup(self):
        """Clean up resources and terminate the program."""
        self.launcher.cleanup()
        self.x11.close()


def main():
    parser = argparse.ArgumentParser(
        description='X11 Mouse Automation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ./mouse.py "leafpad" script.txt
  ./mouse.py "gedit" -c "<click:100,200>" -c "<wait:1>"
  ./mouse.py --attach leafpad -c "<click:100,200>"
  ./mouse.py "firefox" -c "<drag:100,100:200,200>" -c "<scroll:down:3>"

Script commands:
  <click:100,200>       Left click at screen coordinates (100, 200)
  <rightclick:100,200>  Right click at coordinates
  <dblclick:100,200>    Double click at coordinates
  <move:100,200>        Move cursor to coordinates
  <drag:100,200:500,600> Drag from (100,200) to (500,600)
  <scroll:up:3>         Scroll up 3 clicks
  <scroll:down:5>       Scroll down 5 clicks
  <wait:2>              Wait 2 seconds
  # comment             Ignored
        """
    )

    parser.add_argument('program', nargs='?', help='Program to launch (in quotes if has args)')
    parser.add_argument('script', nargs='?', help='Script file to execute')
    parser.add_argument('-c', '--command', action='append', dest='commands',
                        help='Execute single command (can be repeated)')
    add_window_args(parser)
    add_delay_args(parser)
    add_debug_args(parser)
    add_attach_args(parser)
    parser.add_argument('-n', '--no-wait', action='store_true',
                        help='Exit immediately after script (don\'t wait for program)')

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
        parser.error("Either program or --attach/--attach-window-id is required")

    attach_pid = args.attach
    attach_window_id = args.attach_window_id

    if not args.script and not args.commands:
        parser.error("Either script file or -c command required")

    auto = MouseAutomation(
        program_cmd=args.program,
        startup_delay=args.delay,
        event_delay=args.typing_delay,
        window_name=args.window,
        debug=args.debug,
        attach_pid=attach_pid,
        attach_window_id=attach_window_id,
    )

    try:
        if args.program:
            if not auto.start_program():
                print("\nFailed to find window. Exiting.")
                return 1
        else:
            # Attach mode: find existing window
            if attach_window_id:
                wid = int(attach_window_id, 0)
                from Xlib import display as xdisplay
                d = xdisplay.Display()
                auto.window = d.create_resource_object('window', wid)
                auto.window_valid = True
                print(f"Attached to window: {hex(wid)}")
            elif attach_pid:
                auto.window = auto.finder.find_by_pid(attach_pid)
                if auto.window:
                    auto.window_valid = True
                    print(f"Attached to window: {hex(auto.window.id)}")
                else:
                    print("ERROR: Could not find window by PID")
                    return 1
            elif args.window:
                auto.window = auto.finder.find(args.window, strategy='name')
                if auto.window:
                    auto.window_valid = True
                    print(f"Attached to window: {hex(auto.window.id)}")
                else:
                    print("ERROR: Could not find window by name")
                    return 1
            else:
                print("ERROR: --attach requires --window or explicit window name")
                return 1

        if args.script:
            auto.run_script_file(args.script)
        elif args.commands:
            auto.run_commands(args.commands)

        if not args.no_wait and args.program:
            auto.wait_for_exit()
        else:
            print("\nScript done.")

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
        auto.cleanup()

    return 0


if __name__ == "__main__":
    sys.exit(main())
