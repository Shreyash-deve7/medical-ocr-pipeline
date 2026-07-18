# Quick Fixes

Common, high-frequency errors with their usual remedies. Verify the fix with a reproduction before declaring victory — do not guess.

## Import / Module Errors
- `ModuleNotFoundError: No module named 'X'`
  - Wrong virtualenv/conda env active → activate the correct environment.
  - Package not installed → `pip install X` / `npm install X`.
  - Running script from wrong directory → use `-m` (`python -m package.module`) or fix `PYTHONPATH`.
- `ImportError: attempted relative import with no known parent package`
  - Run as a module (`python -m`) instead of a script, or fix package structure.

## Port Already in Use
- `Address already in use` / `EADDRINUSE`
  - Find and kill the process: `lsof -i :<port>` (macOS/Linux) or `netstat -ano | findstr :<port>` (Windows), then kill the PID.
  - Or change the port / set `PORT` env var.

## Dependency Version Mismatch
- `AttributeError: module X has no attribute Y` after an upgrade
  - Pin the version that worked: `pip install X==<version>`; check the changelog for breaking changes.
  - Use a lockfile (`requirements.txt` with pins, `package-lock.json`, `poetry.lock`).

## CORS Errors (Browser → API)
- `Blocked by CORS policy: No 'Access-Control-Allow-Origin'`
  - Server must send `Access-Control-Allow-Origin` (and `Allow-Methods`/`Allow-Headers` for preflight).
  - For dev, configure the proxy in `vite.config.ts` / `package.json` `proxy` rather than disabling security.

## Environment Variables Missing
- `KeyError: 'API_KEY'` / `NoneType` from a config lookup
  - Confirm `.env` is loaded (and not gitignored away from the run context).
  - Print `os.environ` keys (not values) to verify what is actually present.

## Database / Connection Refused
- `ConnectionRefusedError` / `ECONNREFUSED`
  - Is the service actually running? `docker ps`, `pg_isready`, `redis-cli ping`.
  - Host/port correct? Localhost vs container network (use the service name in Docker Compose).

## Encoding / Unicode Errors
- `'utf-8' codec can't decode byte`
  - Open files with explicit `encoding='utf-8'`; detect with `chardet` if unknown.
  - Ensure consistent encoding end-to-end (DB, API, file).

## Infinite Loop / Hang
- Add a max-iteration guard or timeout; check loop termination condition and recursion base case.
- For async hangs, check for an un-awaited promise or a deadlocked lock.

## Cache Stale Results
- Bust the cache: clear Redis/`__pycache__`/`node_modules/.cache`, hard-reload the browser, disable HTTP caching during debugging.

## Reminder
These are starting points. Always confirm the actual root cause with a targeted test — a quick fix that masks the symptom will recur.
