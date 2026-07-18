# Debugging Flaky Tests

A flaky test is a test that sometimes passes and sometimes fails without code changes. Never ignore flakiness — it destroys trust in the suite.

## Capture Evidence

Enable traces and screenshots so failures are debuggable:

```ts
// playwright.config.ts
use: {
  trace: 'on-first-retry',
  screenshot: 'only-on-failure',
  video: 'retain-on-failure',
}
```

```bash
# Re-run with retries to capture a trace
npx playwright test --retries=2

# Inspect the timeline (network, DOM, console) in the trace viewer
npx playwright show-trace test-results/<test>/trace.zip

# Run many times to confirm instability
npx playwright test --repeat-each=10
```

## Common Causes & Fixes

| Cause | Symptom | Fix |
|-------|---------|-----|
| Arbitrary `waitForTimeout` | Fails intermittently on slow CI | Replace with `waitFor({ state })` or auto-waiting assertions |
| Shared state between tests | Order-dependent failures | Isolate state; use fixtures; reset DB between tests |
| Race with async UI | Element not ready | Use `expect(locator).toBeVisible()` (auto-waits) |
| Brittle CSS selectors | Breaks on restyle | Switch to role/label/test-id locators |
| Animation/timing | Click intercepted | `force: false` + wait for stable; disable animations in test |
| Backend flakiness | Random 500s | Mock the API (see api-mocking) |
| Parallelism collisions | Pass alone, fail in parallel | Use isolated data/users per worker; avoid shared ports |

## Replace Arbitrary Waits

```ts
// ❌ Flaky — fixed delay may be too short or waste time
await page.waitForTimeout(2000);
await page.getByRole('button', { name: 'Save' }).click();

// ✅ Reliable — waits for the actual element state
await page.getByRole('button', { name: 'Save' }).waitFor({ state: 'visible' });
await page.getByRole('button', { name: 'Save' }).click();

// ✅ Best — assertion auto-waits and verifies the outcome
await expect(page.getByRole('status')).toHaveText('Saved');
```

## Debugging Workflow

1. Run the failing test with `--retries=2` and `trace: 'on-first-retry'`.
2. Open the trace: inspect the action timeline, network, and console at the failure point.
3. Identify the root cause from the table above.
4. Apply the targeted fix (proper wait, better locator, isolated state, mock).
5. Verify with `--repeat-each=10` — only mark resolved when it's stable across runs.

## Quarantine vs. Fix

- **Fix immediately** if the cause is clear and local.
- **Quarantine** (skip with a tracked issue) only as a last resort to keep CI green while you investigate — never silently delete or permanently skip a flaky test.

## Anti-patterns
- Relying on `retries` to "pass" flaky tests without fixing the cause.
- Adding `waitForTimeout` to mask a race.
- Deleting the test because it's annoying.
- Using `force: true` clicks to bypass visibility/timing problems (hides real bugs).
