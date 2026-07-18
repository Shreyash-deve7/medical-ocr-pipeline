# Configuration

A well-tuned `playwright.config.ts` prevents most flakiness and makes debugging painless.

## Minimal Config

```ts
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  timeout: 30_000,
  expect: { timeout: 5_000 },
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 4 : undefined,
  reporter: process.env.CI ? [['html', { open: 'never' }], ['github']] : 'list',
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
    { name: 'webkit', use: { ...devices['Desktop Safari'] } },
  ],
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
```

## Key Options

| Option | Purpose |
|--------|---------|
| `baseURL` | Lets you use `page.goto('/login')` instead of full URLs |
| `trace` | `'on-first-retry'` captures traces only when needed (cheap + debuggable) |
| `screenshot` / `video` | Capture on failure for post-mortems |
| `retries` | Auto-retry flaky tests in CI (but fix the root cause, don't rely on it) |
| `fullyParallel` | Run tests in parallel for speed |
| `webServer` | Auto-start your app before tests run |

## Reporters

- `list` — simple console output (local).
- `html` — interactive report with traces/screenshots.
- `github` — annotations in GitHub Actions.
- `junit` — for other CI systems.
- `allure` — rich reporting (separate package).

```ts
reporter: [
  ['html', { open: 'never' }],
  ['junit', { outputFile: 'results.xml' }],
];
```

## Web Server

```ts
webServer: {
  command: 'npm run start',
  url: 'http://localhost:3000',
  reuseExistingServer: !process.env.CI, // use running server locally, start fresh in CI
  timeout: 120_000,
  stdout: 'ignore',
  stderr: 'pipe',
}
```

## Environment-Specific Tuning

- **Local**: `retries: 0`, `workers: undefined` (default), `reuseExistingServer: true`.
- **CI**: `retries: 2`, `forbidOnly: true`, `workers: 4`, `reuseExistingServer: false`, HTML + JUnit reporters.

## Tips

- Set `expect.timeout` lower than `test.timeout` so assertions fail fast with clear messages.
- Use `testIgnore` / `testMatch` to control which files run.
- Keep `trace: 'on-first-retry'` — full tracing on every run is slow and storage-heavy.
