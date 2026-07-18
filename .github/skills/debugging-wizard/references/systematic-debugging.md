# Systematic Debugging

For complex bugs, regressions that resist multiple fixes, or when you keep coming back to the same error. Replace intuition-driven changes with a disciplined loop.

## The Five-Step Method (in depth)

### 1. Reproduce
- Get a deterministic, repeatable trigger. If it only happens "sometimes," you don't have reproduction yet — gather more data first.
- Capture the exact inputs, environment, and steps. Write them down.
- If production-only, build a safe replica (staging, fixture data, recorded traffic) — never experiment on live users.

### 2. Isolate
- Reduce the surface: minimal input, minimal code path, minimal environment.
- Use [strategies](./strategies.md) — binary search, git bisect, differential debugging.
- State the smallest unit that still fails. This is your blast radius.

### 3. Hypothesize and Test
- Write 2–4 candidate causes. Rank by likelihood and ease of testing.
- For each: define ONE experiment that proves or disproves it (breakpoint, assertion, log, unit test).
- Run one experiment at a time. Record the result. Disprove cheaply first.
- Avoid the trap of "fixing" by changing several things — you won't know what worked, and you may introduce a new bug.

### 4. Fix
- Apply the minimal change that addresses the proven root cause.
- Verify the original reproduction now passes.
- Verify you haven't broken adjacent behavior (run the relevant test suite).

### 5. Prevent
- Add a regression test that fails without the fix and passes with it.
- If the bug was a class of error (e.g., missing null check), consider a guard, schema validation, or lint rule.
- Document the root cause in a comment or changelog so the next person doesn't re-litigate it.

## Root Cause Analysis (RCA)

When a bug is serious or recurring, go beyond the immediate fix:

1. **Ask "why" five times** (5 Whys): each answer becomes the next question until you reach a systemic cause, not a symptom.
2. **Distinguish proximate vs root**: "null dereference" is proximate; "we have no schema validation at the API boundary" is root.
3. **Classify**: people (process), process (missing check), technology (tool limitation), or environment.
4. **Action**: a fix for the symptom plus a change that prevents the class of bug.

## Handling Multiple Failed Fixes

If you've already tried several changes without success:
- **Reset to a known state**: revert all speculative edits so you're debugging the original bug, not your own.
- **Re-confirm reproduction**: maybe the bug changed or your repro was wrong.
- **Rebuild the hypothesis list** from evidence, not memory.
- **Get a second perspective**: a fresh reviewer sees assumptions you've stopped questioning.
- **Instrument, don't guess**: add precise observability at the exact failure boundary.

## Evidence Discipline

- Capture the full stack trace and the exact input that triggered it.
- Keep a log of what you tried and what each attempt showed.
- Prefer screenshots/terminal output over paraphrased descriptions when handing off.

## Completion Checklist

- [ ] Reproduction is deterministic and documented.
- [ ] Root cause is proven (not assumed).
- [ ] Fix is minimal and verified against the reproduction.
- [ ] Regression test added.
- [ ] No debug code (logs, breakpoints, prints) left behind.
- [ ] Root cause documented for future reference.
