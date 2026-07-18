# API Mocking

Intercept network traffic to make tests deterministic, fast, and independent of backend state.

## Route Interception

```ts
// Fulfill a request with a stubbed response
await page.route('**/api/user', (route) =>
  route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ id: 1, name: 'Ada' }),
  })
);

// Abort a request (simulate failure)
await page.route('**/api/metrics', (route) => route.abort('failed'));

// Continue with modifications
await page.route('**/api/**', (route) => {
  const headers = { ...route.request().headers(), 'x-test': '1' };
  route.continue({ headers });
});
```

## Mocking with `page.route` vs `context.route`

- `page.route` — applies to one page only.
- `context.route` / `browserContext.route` — applies to all pages in the context (use for global mocks like auth).

## Conditional / Dynamic Mocks

```ts
await page.route('**/api/items', (route) => {
  const url = new URL(route.request().url());
  if (url.searchParams.get('id') === '42') {
    return route.fulfill({ status: 404, body: 'not found' });
  }
  return route.fulfill({ status: 200, body: '{"id":1}' });
});
```

## Mocking GraphQL

```ts
await page.route('**/graphql', (route) => {
  const postData = route.request().postDataJSON();
  if (postData.query.includes('GetUser')) {
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ data: { user: { name: 'Ada' } } }),
    });
  }
  return route.continue();
});
```

## Fixtures for Mocks

```ts
// fixtures.ts
import { test as base } from '@playwright/test';

export const test = base.extend<{ mockApi: void }>({
  mockApi: async ({ context }, use) => {
    await context.route('**/api/**', (route) =>
      route.fulfill({ status: 200, body: '{}' })
    );
    await use();
  },
});

test('uses mocked api', async ({ page, mockApi }) => {
  await page.goto('/');
});
```

## Best Practices

- Mock at the **boundary** (network), not inside app code, so you test the real UI.
- Match URLs with glob (`**/api/user`) or regex for precision.
- Always `route.continue()` for requests you don't want to fully stub, or the call hangs.
- Keep mock data realistic and representative of production shapes.
- Combine with `test.use({ storageState })` to simulate authenticated sessions.
- Don't mock to hide real backend bugs — use mocks for isolation, integration tests for the real path.
