# Feature 04: Script Variable Substitution (`${VAR}`)

## Status
**LOW PRIORITY — nice-to-have; implement LAST after all other features are proven**

## What It Does
Allows users to define variables that get interpolated into script lines before they are executed. Examples:

```
./keypress.py "leafpad" script.txt -w leafpad --var PASSWORD="secret123" --var USER="admin"
```

Script contents:
```
login <tab>
${USER}
<wait:0.5>
<tab>
${PASSWORD}
<Enter>
```

Result: types `login\tadmin\tsecret123\n`.

Also supports defaults:
```
${USER:-defaultuser}
```

## Implementation Steps

1. Add `--var` CLI flag (repeatable):
   ```python
   parser.add_argument('--var', action='append', help='Set script variable (format: KEY=VALUE)')
   ```
2. Parse `--var` entries in `main()`:
   ```python
   script_vars = {}
   if args.var:
       for entry in args.var:
           key, _, value = entry.partition('=')
           script_vars[key] = value
   ```
3. Add `expand_script_vars(lines, script_vars, environ=None)` at module level (top of file, near `expand_script_loops`):
   ```python
   import re
   _VAR_RE = re.compile(r'\$\{(\w+)(?::-(.*?)\})\}')
   
   def _replacer(match, scope, env):
       name = match.group(1)
       default = match.group(2)
       value = scope.get(name)
       if value is None:
           value = env.get(name) if env else None
       if value is None:
           value = default if default else match.group(0)
       return value
   ```
   Actually, use a simpler regex that handles `${VAR}` and `${VAR:-default}`:
   ```python
   import re
   _VAR_RE = re.compile(r'\$\{([^}]+)\}')

   def expand_script_vars(lines, script_vars, environ=None):
       def _replacer(m):
           inner = m.group(1)
           if ':-' in inner:
               name, default = inner.split(':-', 1)
               return script_vars.get(name, environ.get(name, default) if environ else default)
           return script_vars.get(inner, environ.get(inner, m.group(0)) if environ else m.group(0))
       return [_VAR_RE.sub(_replacer, line) for line in lines]
   ```
4. In `run_script_file()`, apply `expand_script_vars()` AFTER loop expansion:
   ```python
   lines = expand_script_loops(raw_lines)
   lines = expand_script_vars(lines, self.script_vars or {}, os.environ)
   ```

## Why This Is Low Priority
- The existing script language is sufficient for 90% of use cases
- This feature doesn't unlock any new capability that `-c` commands don't already provide
- It adds regex processing to every script line which introduces a small performance and complexity cost
- More importantly: this feature was BUNDLED with compose fallback in our failed attempt, making the root cause of failures harder to find. Isolation is the lesson.

## Safety Rules
- `expand_script_vars()` must be a PURE FUNCTION — no side effects, no X11 calls, no class state mutation
- It must work IDENTICALLY on `run_script_file()` and `run_commands()` (if users request it there later)
- The regex must NOT consume normal `$` characters that are NOT followed by `{`

## Test Plan

| Step | Script | Expected |
|------|--------|---------|
| 1 | `--var X=hello` + `${X}` in script | Types `hello` |
| 2 | `--var Y=world` + `${MISSING:-default}` | Types `default` |
| 3 | `python3 test_loops.py && python3 test_integration.py` | 15 + 11 pass |

## Estimated Diff Size
~25 lines: 8 lines for `expand_script_vars()`, 5 lines for `--var` argparse, 12 lines for integration into `run_script_file()` and `main()`.
