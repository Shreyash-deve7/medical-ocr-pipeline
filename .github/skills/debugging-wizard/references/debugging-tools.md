# Debugging Tools

Set up the right tooling for the language you are debugging. Prefer an interactive debugger over print statements — it lets you inspect state at exact points without editing code.

## Python

### pdb (built-in)
```
python -m pdb script.py
# b <line>      set breakpoint
# b <file>:<line>
# c             continue to next breakpoint
# n             step over
# s             step into
# r             return from current function
# p <expr>      print expression
# pp <expr>     pretty-print
# bt            backtrace
# l             list source around current line
# q             quit
```
Set breakpoints programmatically with `import pdb; pdb.set_trace()` (or `breakpoint()` in Python 3.7+).

### debugpy (VS Code / remote)
```
pip install debugpy
python -m debugpy --listen 5678 --wait-for-client script.py
```
Attach from VS Code via the "Python: Remote Attach" debug configuration.

### pytest debugging
```
pytest test_file.py::test_name --pdb          # drop into pdb on failure
pytest test_file.py::test_name --trace        # break at first line
pytest test_file.py::test_name -x --pdb       # break on first failure
```

## JavaScript / TypeScript (Node.js)

### CLI inspector
```
node --inspect-brk script.js     # pause at first line
node --inspect script.js         # break on first statement of entry
```
Open `chrome://inspect` in Chrome → "Open dedicated DevTools for Node".

### VS Code launch.json
```json
{
  "type": "node",
  "request": "launch",
  "name": "Debug script",
  "program": "${workspaceFolder}/script.js",
  "console": "integratedTerminal"
}
```

### Browser (frontend)
Use the built-in DevTools Sources panel: breakpoints, conditional breakpoints (right-click → "Add conditional breakpoint"), watch expressions, and the Console for live evaluation. For async issues, enable "Async stack traces" in the Call Stack pane.

## Go

```
dlv debug ./cmd/server           # build & debug
dlv test ./pkg/...               # debug tests
dlv attach <pid>                 # attach to running process
# (dlv) break main.go:55
# (dlv) continue
# (dlv) print myVar
# (dlv) locals
# (dlv) stack
```

## Logging & Tracing (language-agnostic)

When a debugger cannot attach (production, distributed systems, async pipelines):

- **Structured logging**: emit JSON logs with `level`, `timestamp`, `trace_id`, and `span_id` so entries can be correlated.
- **Distributed tracing**: OpenTelemetry / Jaeger to follow a request across services.
- **Log levels**: temporarily raise verbosity (`DEBUG`) on the suspect module only — avoid flooding global logs.
- **Correlation IDs**: stamp every log line with the request/job ID so you can grep the full execution path.

## Quick Setup Checklist

1. Confirm you can run the code locally and hit a breakpoint.
2. Reproduce the failure under the debugger (not just in production).
3. Set breakpoints at the entry of the failing function and at boundaries (I/O, network, parsing).
4. Step through, watching the variables that the hypothesis concerns.
5. Capture the minimal failing input for a regression test.
