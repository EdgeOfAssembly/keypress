#!/usr/bin/env python3
"""
Dead-key and compose sequence support for X11 keyboard automation.

Parses X11 Compose files to build a cache of key sequences that produce
special characters like é, ñ, ç, — (em-dash), etc.
"""

import os
import re
import sys
from typing import Optional


KEYNAME_TO_X11 = {
    "apostrophe": "'", "quotedbl": '"', "minus": "-", "period": ".", "comma": ",",
    "slash": "/", "backslash": "\\", "asciitilde": "~", "asciicircum": "^",
    "ampersand": "&", "parenleft": "(", "parenright": ")", "asterisk": "*",
    "underscore": "_", "plus": "+", "equal": "=", "colon": ":", "semicolon": ";",
    "question": "?", "exclam": "!", "at": "@", "numbersign": "#", "dollar": "$",
    "percent": "%", "less": "<", "greater": ">", "bar": "|", "braceleft": "{",
    "braceright": "}", "bracketleft": "[", "bracketright": "]",
    "space": " ", "Tab": "Tab", "Return": "Return", "Escape": "Escape",
    "Delete": "Delete", "BackSpace": "BackSpace",
    # Letters pass through as-is
    "A": "A", "B": "B", "C": "C", "D": "D", "E": "E", "F": "F", "G": "G",
    "H": "H", "I": "I", "J": "J", "K": "K", "L": "L", "M": "M", "N": "N",
    "O": "O", "P": "P", "Q": "Q", "R": "R", "S": "S", "T": "T", "U": "U",
    "V": "V", "W": "W", "X": "X", "Y": "Y", "Z": "Z",
    "a": "a", "b": "b", "c": "c", "d": "d", "e": "e", "f": "f", "g": "g",
    "h": "h", "i": "i", "j": "j", "k": "k", "l": "l", "m": "m", "n": "n",
    "o": "o", "p": "p", "q": "q", "r": "r", "s": "s", "t": "t", "u": "u",
    "v": "v", "w": "w", "x": "x", "y": "y", "z": "z",
    # Numbers pass through
    "0": "0", "1": "1", "2": "2", "3": "3", "4": "4",
    "5": "5", "6": "6", "7": "7", "8": "8", "9": "9",
    # Dead keys mapped to base character for simulation
    "dead_grave": "`", "dead_acute": "'", "dead_circumflex": "^",
    "dead_tilde": "~", "dead_diaeresis": '"', "dead_cedilla": ",",
    "dead_abovering": "o", "dead_macron": "-", "dead_breve": "u",
    "dead_dotabove": ".", "dead_doubleacute": '"', "dead_caron": "v",
    "dead_belowdot": ".",
}


class ComposeCache:
    """
    Cache for X11 compose sequences.

    Parses X11 Compose files to build a mapping from characters to the
    key sequences needed to produce them via compose/dead-key input.
    """

    def __init__(self, display=None, compose_key=None):
        """
        Initialize the compose cache.

        Args:
            display: Optional X11 display instance for compose key detection
            compose_key: Key to use for Multi_key sequences (default: "Alt_R")
        """
        self.display = display
        self.compose_key = compose_key or "Alt_R"
        self.cache: dict[str, list[str]] = {}
        self._built = False
        self._parse_errors: list[str] = []
        self._compose_file: Optional[str] = None

    def find_compose_file(self) -> Optional[str]:
        """
        Search for a Compose file in standard locations.

        Searches in order:
        1. ~/.XCompose
        2. /usr/share/X11/locale/*/Compose (prefer UTF-8)
        3. /usr/share/X11/locale/en_US.UTF-8/Compose (fallback)

        Returns:
            Path to compose file if found, None otherwise
        """
        # Check user compose file first
        home_compose = os.path.expanduser("~/.XCompose")
        if os.path.isfile(home_compose):
            return home_compose

        # Search system compose files
        locale_dir = "/usr/share/X11/locale"
        if not os.path.isdir(locale_dir):
            return None

        # Prefer UTF-8 locales
        utf8_compose = None
        fallback_compose = None

        try:
            for entry in os.listdir(locale_dir):
                compose_path = os.path.join(locale_dir, entry, "Compose")
                if os.path.isfile(compose_path):
                    if "UTF-8" in entry or "utf8" in entry.lower():
                        if utf8_compose is None:
                            utf8_compose = compose_path
                    if entry == "en_US.UTF-8":
                        fallback_compose = compose_path
        except OSError:
            pass

        if utf8_compose:
            return utf8_compose
        if fallback_compose:
            return fallback_compose

        # Return any compose file found
        try:
            for entry in os.listdir(locale_dir):
                compose_path = os.path.join(locale_dir, entry, "Compose")
                if os.path.isfile(compose_path):
                    return compose_path
        except OSError:
            pass

        return None

    def build_cache(self) -> int:
        """
        Parse compose file and build the cache.

        Handles 'include' directives, skips comments and blank lines.
        Stores first-seen sequence per character (prefer simpler sequences).

        Returns:
            Number of entries in the cache
        """
        self.cache = {}
        self._parse_errors = []
        self._built = False

        compose_file = self.find_compose_file()
        if not compose_file:
            print(f"Warning: No compose file found", file=sys.stderr)
            return 0

        self._compose_file = compose_file

        try:
            with open(compose_file, "r", encoding="utf-8", errors="replace") as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        result = self.parse_compose_line(line)
                        if result:
                            keys, char = result
                            # Store first-seen (simpler) sequence
                            if char not in self.cache:
                                self.cache[char] = keys
                    except Exception as e:
                        self._parse_errors.append(
                            f"Line {line_num}: {str(e)}"
                        )
        except OSError as e:
            print(f"Warning: Could not read compose file: {e}", file=sys.stderr)
            return 0

        self._built = True
        return len(self.cache)

    def get_sequence(self, char: str) -> Optional[list[str]]:
        """
        Get the key sequence to produce a character.

        Args:
            char: The character to type

        Returns:
            List of X11 key names to simulate, or None if not available
        """
        if not self._built:
            self.build_cache()
        return self.cache.get(char)

    def can_type(self, char: str) -> bool:
        """
        Check if a character can be typed via compose sequence.

        Args:
            char: The character to check

        Returns:
            True if the character has a compose sequence
        """
        if not self._built:
            self.build_cache()
        return char in self.cache

    def get_debug_info(self) -> str:
        """
        Get formatted statistics and sample entries.

        Returns:
            Multi-line string with cache statistics and samples
        """
        if not self._built:
            return "Cache not built"

        lines = [
            f"Compose Cache Statistics",
            f"======================",
            f"Compose file: {self._compose_file or 'None'}",
            f"Total entries: {len(self.cache)}",
            f"Parse errors: {len(self._parse_errors)}",
            f"",
            f"Sample entries:",
        ]

        # Show up to 10 sample entries
        samples = list(self.cache.items())[:10]
        for char, keys in samples:
            lines.append(f"  {repr(char)}: {' '.join(keys)}")

        if self._parse_errors:
            lines.append("")
            lines.append("Parse errors (first 5):")
            for err in self._parse_errors[:5]:
                lines.append(f"  {err}")

        return "\n".join(lines)

    def get_all_characters(self) -> list[str]:
        """
        Get all characters available in the cache.

        Returns:
            List of all characters that can be typed
        """
        if not self._built:
            self.build_cache()
        return list(self.cache.keys())

    def parse_compose_line(self, line: str) -> Optional[tuple[list[str], str]]:
        """
        Parse one line from a compose file.

        Format: <key> <key> ... : "char" keysym
        or: <key> <key> ... : U+XXXX description

        Args:
            line: Line from compose file

        Returns:
            Tuple of (key_sequence, character) or None if not parseable
        """
        line = line.strip()

        # Skip comments and blank lines
        if not line or line.startswith("#"):
            return None

        # Handle include directives
        if line.startswith("include"):
            self._handle_include(line)
            return None

        # Parse sequence: keys : "char" or keys : U+XXXX
        if ":" not in line:
            return None

        try:
            seq_part, result_part = line.split(":", 1)
            seq_part = seq_part.strip()
            result_part = result_part.strip()

            if not seq_part or not result_part:
                return None

            keys = self._parse_key_sequence(seq_part)
            char = self._parse_result_character(result_part)

            if keys and char:
                return (keys, char)
        except Exception:
            pass

        return None

    def _handle_include(self, line: str) -> None:
        """Handle include directive (simplified - just note it)."""
        # Full include handling would recursively parse included files
        # For now, we just acknowledge the directive
        pass

    def _parse_key_sequence(self, seq_part: str) -> list[str]:
        """
        Parse the key sequence part of a compose line.

        Args:
            seq_part: The keys portion (before the colon)

        Returns:
            List of X11 key names
        """
        keys = []

        # Split on whitespace, handling quoted strings
        tokens = self._tokenize(seq_part)

        for token in tokens:
            x11_name = keyname_to_x11(token, self.compose_key)
            if x11_name:
                keys.append(x11_name)

        return keys

    def _tokenize(self, text: str) -> list[str]:
        """
        Tokenize a string, respecting quoted substrings.

        Args:
            text: String to tokenize

        Returns:
            List of tokens
        """
        tokens = []
        current = ""
        in_quotes = False
        quote_char = None

        for char in text:
            if char in '"\'':
                if not in_quotes:
                    in_quotes = True
                    quote_char = char
                elif char == quote_char:
                    in_quotes = False
                    quote_char = None
                else:
                    current += char
            elif char.isspace() and not in_quotes:
                if current:
                    tokens.append(current)
                    current = ""
            else:
                current += char

        if current:
            tokens.append(current)

        return tokens

    def _parse_result_character(self, result_part: str) -> Optional[str]:
        """
        Parse the result character from a compose line.

        Handles:
        - "quoted" strings
        - U+XXXX unicode escapes
        - Single characters

        Args:
            result_part: The result portion (after the colon)

        Returns:
            The character string, or None if not parseable
        """
        result_part = result_part.strip()

        # Handle quoted string: "char" or 'char'
        if (result_part.startswith('"') and result_part.endswith('"')) or \
           (result_part.startswith("'") and result_part.endswith("'")):
            return result_part[1:-1]

        # Handle Unicode escape: U+XXXX or U+XXXXX
        match = re.match(r'U\+([0-9A-Fa-f]+)', result_part)
        if match:
            try:
                codepoint = int(match.group(1), 16)
                return chr(codepoint)
            except (ValueError, OverflowError):
                pass

        # Handle hex escape: <hex>
        match = re.match(r'<([0-9A-Fa-f]+)>', result_part)
        if match:
            try:
                codepoint = int(match.group(1), 16)
                return chr(codepoint)
            except (ValueError, OverflowError):
                pass

        # Handle single character or keysym name at end
        # Try to extract the actual character from keysym references
        parts = result_part.split()
        if parts:
            first = parts[0]
            # If it's a single character, return it
            if len(first) == 1:
                return first
            # Try to handle keysym names like "eacute"
            char = self._keysym_to_char(first)
            if char:
                return char

        return None

    def _keysym_to_char(self, keysym: str) -> Optional[str]:
        """
        Convert a keysym name to its character.

        Args:
            keysym: Keysym name like "eacute", "ntilde", etc.

        Returns:
            The corresponding character, or None
        """
        # Common keysym to character mappings
        keysym_map = {
            "eacute": "é", "Eacute": "É",
            "ntilde": "ñ", "Ntilde": "Ñ",
            "ccedilla": "ç", "Ccedilla": "Ç",
            "udiaeresis": "ü", "Udiaeresis": "Ü",
            "odieresis": "ö", "Odieresis": "Ö",
            "adieresis": "ä", "Adieresis": "Ä",
            "udiaeresis": "ü", "udieresis": "ü",
            "oslash": "ø", "Oslash": "Ø",
            "ae": "æ", "AE": "Æ",
            "ssharp": "ß",
            "THORN": "Þ", "thorn": "þ",
            "ETH": "Ð", "eth": "ð",
            "currency": "¤", "yen": "¥",
            "sterling": "£", "cent": "¢",
            "EuroSign": "€", "euro": "€",
            "copyright": "©", "registered": "®",
            "trademark": "™",
            "degree": "°",
            "onehalf": "½", "onequarter": "¼", "threequarters": "¾",
            "oned eighth": "⅛",
            "ellipsis": "…",
            "emdash": "—", "endash": "–",
            "guillemotleft": "«", "guillemotright": "»",
            "iexcl": "¡", "questiondown": "¿",
        }
        return keysym_map.get(keysym)


def keyname_to_x11(name: str, compose_key: str = "Alt_R") -> str:
    """
    Convert a compose key name to X11 name.

    Args:
        name: Key name from compose file
        compose_key: Key to use for Multi_key sequences

    Returns:
        X11 key name for simulation
    """
    # Handle Multi_key specially
    if name == "Multi_key":
        return compose_key

    # Direct lookup
    if name in KEYNAME_TO_X11:
        return KEYNAME_TO_X11[name]

    # Remove wrapping <...> if present and re-lookup
    if name.startswith("<") and name.endswith(">"):
        inner = name[1:-1]
        if inner in KEYNAME_TO_X11:
            return KEYNAME_TO_X11[inner]
        return inner

    # Default: return name as-is
    return name


if __name__ == "__main__":
    # Create and build cache
    cache = ComposeCache()
    count = cache.build_cache()

    print(f"Compose cache built: {count} entries")
    print(f"Compose file: {cache._compose_file or 'None found'}")
    print()

    # Test common characters
    test_chars = ["é", "ñ", "ç", "ü", "ö", "ä", "—", "…", "°", "½", "€", "£", "©"]
    print("Testing common characters:")
    print("-" * 50)

    for char in test_chars:
        seq = cache.get_sequence(char)
        if seq:
            print(f"  {char}: {' '.join(seq)}")
        else:
            print(f"  {char}: (no sequence)")

    print()

    # Print debug info
    print(cache.get_debug_info())
    print()

    # Handle command-line arguments for character lookups
    if len(sys.argv) > 1:
        print("Command-line lookups:")
        print("-" * 50)
        for arg in sys.argv[1:]:
            # Handle escape sequences
            try:
                char = arg.encode().decode('unicode_escape')
            except UnicodeDecodeError:
                char = arg

            seq = cache.get_sequence(char)
            if seq:
                print(f"  {repr(char)} ({char}): {' '.join(seq)}")
            else:
                print(f"  {repr(char)} ({char}): (no sequence)")
