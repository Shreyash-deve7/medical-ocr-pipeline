# Common Bug Patterns

Recognize these recurring shapes so you can form hypotheses faster. Each pattern lists typical symptoms and where to look.

## Off-by-One
- **Symptoms**: loop processes one too many/few items; index out of range at the last element; fencepost errors.
- **Look**: `<` vs `<=`, `range(n)` vs `range(1, n)`, inclusive/exclusive slice bounds, 0-based vs 1-based indexing.

## Null / None / Undefined Handling
- **Symptoms**: `AttributeError: 'NoneType'`, `TypeError: cannot read property of undefined`, `NullPointerException`.
- **Look**: functions that return `None` on missing data, optional chaining missing, uninitialized fields, failed lookups that fall through silently.

## Race Conditions & Concurrency
- **Symptoms**: intermittent failures, different results on each run, "works on my machine", data corruption under load.
- **Look**: shared mutable state without locks, unsynchronized caches, async/await missing `await`, promise ordering, thread-unsafe collections.

## Type Coercion & Mismatched Types
- **Symptoms**: `"5" + 3 == "53"`, comparing strings to numbers, `NaN` propagation, JSON numbers parsed as strings.
- **Look**: implicit coercion, untyped boundaries (API/DB/CLI), schema drift between producer and consumer.

## Resource Leaks
- **Symptoms**: memory grows over time, file descriptors exhausted, "too many open files", slow degradation.
- **Look**: unclosed files/sockets/connections, missing `finally`/`with`/RAII, unbounded caches, forgotten timers/listeners.

## Configuration & Environment
- **Symptoms**: works locally but not in CI/prod; behavior changes between machines.
- **Look**: env vars, `.env` loading order, missing secrets, hardcoded paths, timezone/locale, feature flags, differing dependency versions.

## Async / Await Mistakes
- **Symptoms**: returns a pending promise, function runs before data ready, "undefined" in output.
- **Look**: missing `await`, `forEach` with async callback, swallowed rejections, not awaiting `Promise.all`.

## State Mutation Surprises
- **Symptoms**: changing one object changes another unexpectedly; cached value is stale.
- **Look**: shared references, mutable default arguments (Python `def f(x=[])`), in-place sort/filter, shallow copies.

## Boundary & Edge Cases
- **Symptoms**: fails on empty input, single item, very large input, Unicode/emoji, special characters.
- **Look**: empty collections, division by zero, max integer overflow, encoding mismatches.

## Silent Failures
- **Symptoms**: no error but wrong result; `try/except` that swallows exceptions; empty `catch` blocks.
- **Look**: broad `except Exception: pass`, ignored return codes, errors logged but not surfaced.

## Hypothesis Shortcut

When you see a symptom, write the most likely pattern as a hypothesis, then prove/disprove it with one targeted check (breakpoint, assertion, or log) before moving on.
