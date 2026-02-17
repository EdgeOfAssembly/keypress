#!/usr/bin/env python3
"""
Dump all keyboard mappings from X11
"""

from Xlib import display, XK

def keysym_to_char(keysym):
    """Convert keysym to character"""
    # Manual mapping for common symbols
    KEYSYM_MAP = {
        0x0020: ' ', 0x0021: '!', 0x0022: '"', 0x0023: '#', 0x0024: '$',
        0x0025: '%', 0x0026: '&', 0x0027: "'", 0x0028: '(', 0x0029: ')',
        0x002a: '*', 0x002b: '+', 0x002c: ',', 0x002d: '-', 0x002e: '.',
        0x002f: '/', 0x003a: ':', 0x003b: ';', 0x003c: '<', 0x003d: '=',
        0x003e: '>', 0x003f: '?', 0x0040: '@', 0x005b: '[', 0x005c: '\\',
        0x005d: ']', 0x005e: '^', 0x005f: '_', 0x0060: '`', 0x007b: '{',
        0x007c: '|', 0x007d: '}', 0x007e: '~',
    }
    
    if keysym in KEYSYM_MAP:
        return KEYSYM_MAP[keysym]
    
    # Try XK.keysym_to_string
    char = XK.keysym_to_string(keysym)
    if char and len(char) == 1:
        return char
    
    return None

def main():
    d = display.Display()
    
    # Get keycode range
    min_keycode = 8
    max_keycode = 255
    
    print(f"Keycode range: {min_keycode}-{max_keycode}")
    print("\n" + "="*80)
    
    # Get keyboard mapping
    keymap = d.get_keyboard_mapping(min_keycode, max_keycode - min_keycode + 1)
    
    print(f"Total keycodes: {len(keymap)}")
    print("="*80)
    
    # Dump all mappings
    for keycode in range(min_keycode, max_keycode + 1):
        index = keycode - min_keycode
        if index >= len(keymap):
            continue
        
        keysyms = keymap[index]
        if not keysyms or all(ks == 0 for ks in keysyms):
            continue
        
        print(f"\nKeycode {keycode}:")
        for col_idx, keysym in enumerate(keysyms[:4]):
            if keysym == 0:
                continue
            
            char = keysym_to_char(keysym)
            keysym_name = XK.keysym_to_string(keysym)
            
            modifier = ['Normal', 'Shift', 'AltGr', 'Shift+AltGr'][col_idx]
            
            char_display = f"'{char}'" if char else 'None'
            name_display = f"({keysym_name})" if keysym_name else ""
            
            print(f"  Col {col_idx} [{modifier:12}]: keysym=0x{keysym:04x} char={char_display:6} {name_display}")
    
    print("\n" + "="*80)
    print("Looking for specific characters:")
    print("="*80)
    
    # Search for specific characters
    search_chars = ['[', ']', '\\', '{', '}', '|', '/', '-', '=']
    search_keysyms = [0x5b, 0x5d, 0x5c, 0x7b, 0x7d, 0x7c, 0x2f, 0x2d, 0x3d]
    
    for search_char, search_keysym in zip(search_chars, search_keysyms):
        print(f"\nSearching for '{search_char}' (keysym 0x{search_keysym:04x}):")
        found = False
        
        for keycode in range(min_keycode, max_keycode + 1):
            index = keycode - min_keycode
            if index >= len(keymap):
                continue
            
            keysyms = keymap[index]
            if not keysyms:
                continue
            
            for col_idx, keysym in enumerate(keysyms[:4]):
                if keysym == search_keysym:
                    modifier = ['Normal', 'Shift', 'AltGr', 'Shift+AltGr'][col_idx]
                    print(f"  FOUND: Keycode {keycode}, Column {col_idx} ({modifier})")
                    found = True
        
        if not found:
            print(f"  NOT FOUND in keymap!")

if __name__ == "__main__":
    main()