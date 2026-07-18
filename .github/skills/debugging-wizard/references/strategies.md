# Debugging Strategies

When the cause is not obvious, use a structured search strategy instead of random changes.

## Binary Search (Divide and Conquer)
Narrow the failing region by repeatedly halving it.
- **Code**: comment out / disable half the logic; if it still fails, the bug is in the other half. Repeat.
- **Data**: bisect the input — remove half the records/lines; find the minimal input that still triggers the failure.
- **Time**: if a value was correct at time T1 and wrong at T2, check the midpoint.

Fastest when the failure is deterministic and you can toggle pieces independently.

## Git Bisect (Regression Hunting)
Find the exact commit that introduced a bug.
```
git bisect start
git bisect bad                 # current HEAD is broken
git bisect good v1.2.0         # last known-good commit/tag
# Git checks out the midpoint. Build/test:
git bisect good                # if it works
git bisect bad                 # if it fails
# Repeat until the first bad commit is printed
git bisect reset
```
Automate the test with `git bisect run <script>` where the script exits 0 for good, 1 for bad.

## Time Travel / Replay Debugging
- **Record & replay**: tools like rr (Linux), WinDbg time travel, or deterministic simulators let you step backward.
- **Replay logs**: feed the exact captured input/request back into the system to reproduce deterministically.
- Useful for non-deterministic, hard-to-reproduce concurrency bugs.

## Minimal Reproduction
Strip the problem to the smallest standalone case:
1. Delete dependencies, frameworks, and unrelated modules.
2. Replace external services with stubs/fixtures.
3. Reduce the input to the smallest trigger.
A minimal repro is also your first regression test.

## Rubber Duck
Explain the execution step-by-step to an inanimate object (or write it as a comment). Vocalizing forces you to state assumptions; the gap between "what should happen" and "what the code does" often reveals the bug.

## Differential Debugging
Compare the broken case against a known-working similar case:
- Same code, different input → isolate input-driven cause.
- Different code, same input → isolate code-driven cause.
- Different environment → isolate environment cause.

## Hypothesis Board
Maintain a running list:
| # | Hypothesis | Test | Result |
|---|-----------|------|--------|
| 1 | Null returned from lookup | Add assert not None | DISPROVEN |
| 2 | Off-by-one in loop | Print index at boundary | PROVEN |

Test one at a time. Cross off disproven theories so you don't re-test them.

## When Stuck
- Sleep on it / switch context — the brain pattern-matches offline.
- Ask for a second opinion (pair debug or a fresh reviewer).
- Re-read the documentation for the API/library you assume you understand.
- Question your assumptions, especially about "impossible" code paths.
