# keypress.py Examples

This directory contains example scripts demonstrating keypress.py features.

## Files

### leafpad_test.txt
Comprehensive test script showing:
- Symbol typing (brackets, backslashes, special chars)
- Special keys (Esc, Tab, Backspace)
- Key combinations (Ctrl+C, Ctrl+V)
- Wait commands
- Function keys
- Finnish layout symbols testing

**Usage:**
```bash
./keypress.py "leafpad /tmp/test_output.txt" examples/leafpad_test.txt -w leafpad
```

Then check `/tmp/test_output.txt` to verify all symbols typed correctly.

### dosbox_commands.txt
DOSBox-X automation example showing:
- Mounting drives
- Directory navigation
- File creation
- Batch file execution
- Timing control

**Usage:**
```bash
./keypress.py "dosbox-x" examples/dosbox_commands.txt -w DOSBox --emulator-mode -d 3
```

**Important:** Use `--emulator-mode` for DOSBox-X!

## Creating Your Own Scripts

### Basic Structure

```
# Comment lines start with #
command one
command two
<special_key>
```

Each line is typed followed by Enter, unless `<nowait>` is used.

### Special Commands Reference

**Keys:**
- `<Esc>`, `<Tab>`, `<Backspace>`, `<Delete>`
- `<Return>`, `<Enter>`, `<Space>`
- `<Up>`, `<Down>`, `<Left>`, `<Right>`
- `<Home>`, `<End>`, `<PageUp>`, `<PageDown>`
- `<F1>` through `<F12>`

**Combinations:**
- `<Ctrl+c>`, `<Ctrl+v>`, `<Ctrl+a>`, etc.
- `<Alt+F4>`, `<Shift+Insert>`
- Any modifier + any key: `<Ctrl+Alt+Del>`

**Timing:**
- `<wait:2>` - Wait 2 seconds
- `<wait:0.5>` - Wait 500 milliseconds

**Flow Control:**
- `<nowait>` - Don't press Enter after previous line

### Tips

1. **Add delays for slow apps:**
   ```
   <wait:3>
   # App should be loaded now
   ```

2. **Use window names:**
   ```bash
   ./keypress.py "myapp" script.txt -w "My Application"
   ```

3. **Adjust typing speed:**
   ```bash
   ./keypress.py "app" script.txt -t 0.1  # Slower (100ms per key)
   ./keypress.py "app" script.txt -t 0.01 # Faster (10ms per key)
   ```

4. **Test with debug mode:**
   ```bash
   ./keypress.py "leafpad" script.txt --debug
   ```

5. **Use nowait for multi-key sequences:**
   ```
   Type this
   <nowait>
    and continue on same line
   ```

## Example Use Cases

### GUI Testing
```bash
# test_suite.sh
for test in tests/*.txt; do
    ./keypress.py "myapp" "$test" -w MyApp -n
    sleep 2
done
```

### Demo Recording
```bash
# demo.txt with slow typing
Introduction text here
<wait:2>
Show important command
<Ctrl+c>
```

### Batch Processing
```bash
# process_files.sh
for file in *.dat; do
    echo "load $file" > /tmp/commands.txt
    echo "process" >> /tmp/commands.txt
    echo "<Ctrl+s>" >> /tmp/commands.txt
    ./keypress.py "myapp" /tmp/commands.txt -w MyApp
done
```

### Accessibility
```bash
# Frequent action as script
./keypress.py "browser" bookmark_sequence.txt -w Firefox
```

## Debugging Scripts

If your script doesn't work:

1. **Test each line individually:**
   ```bash
   ./keypress.py "app" -c "first line" -w App
   ./keypress.py "app" -c "second line" -w App
   ```

2. **Check window detection:**
   ```bash
   # List all windows
   xdotool search --name ""
   
   # Find your app
   xdotool search --name "leafpad"
   ```

3. **Increase startup delay:**
   ```bash
   ./keypress.py "app" script.txt -d 5  # Wait 5 seconds
   ```

4. **Use debug mode:**
   ```bash
   ./keypress.py "app" script.txt --debug
   ```

5. **Check for layout issues:**
   ```bash
   # For normal apps - don't use --emulator-mode
   ./keypress.py "leafpad" script.txt
   
   # For emulators - must use --emulator-mode
   ./keypress.py "dosbox-x" script.txt --emulator-mode
   ```

## Contributing Examples

Have a cool use case? Add your example script:

1. Create `yourexample.txt` in this directory
2. Add documentation to this README
3. Test it works on your layout
4. Submit a pull request!

Good examples to add:
- Game automation
- Software installation sequences
- Configuration file editing
- Terminal command sequences
- Multi-step workflows