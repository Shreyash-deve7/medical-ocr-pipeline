# Selectors & Locators

Selectors are the #1 cause of brittle, flaky tests. Prefer resilient, semantic locators over styling-based ones.

## Locator Priority (best → worst)

1. **Role-based** — `getByRole('button', { name: 'Submit' })`. Resilient to styling and DOM changes; reflects accessibility.
2. **Label / placeholder / text** — `getByLabel('Email')`, `getByPlaceholder('Search')`, `getByText('Sign in')`.
3. **Test id** — `getByTestId('submit-btn')`. Stable if you control the markup; add `data-testid` intentionally.
4. **CSS / XPath** — `locator('.btn-primary')`, `locator('//div[@class=...]')`. Brittle; avoid unless nothing else works.

## Role-Based Selectors (preferred)

```ts
await page.getByRole('button', { name: 'Submit' }).click();
await page.getByRole('link', { name: 'Home' }).click();
await page.getByRole('textbox', { name: 'Search' }).fill('query');
await page.getByRole('checkbox', { name: 'Accept terms' }).check();
```
- `name` matches accessible name (visible text, aria-label, aria-labelledby).
- Use `{ exact: true }` to avoid partial-match surprises.

## Label / Text / Placeholder

```ts
await page.getByLabel('Email address').fill('user@example.com');
await page.getByPlaceholder('you@example.com').fill('user@example.com');
await page.getByText('Welcome back').click();
```

## Test IDs

```ts
// markup: <button data-testid="submit-btn">Submit</button>
await page.getByTestId('submit-btn').click();
```
Configure a custom prefix if needed:
```ts
// playwright.config.ts
use: { testIdAttribute: 'data-pw' };
```

## Filtering & Chaining

```ts
// narrow a locator by another locator or text
await page.getByRole('listitem').filter({ hasText: 'Active' }).click();
await page.getByRole('row').filter({ has: page.getByRole('button', { name: 'Delete' }) }).click();

// locate within a region
const dialog = page.getByRole('dialog');
await dialog.getByRole('button', { name: 'OK' }).click();
```

## Avoid These

- `page.locator('.class')` for anything that can be restyled.
- `first()` / `nth()` without a reason — they hide intent and break on reordering. Prefer `filter()` or a more specific role/text.
- Positional selectors (`div > div:nth-child(3)`) — extremely brittle.
- `waitForTimeout()` to "wait for" an element — use `waitFor({ state })` or auto-waiting assertions instead.

## Locator Best Practices

- Define locators once (in a Page Object) so a markup change means one edit.
- Locators are lazy — they resolve at action time, so they always target the current DOM.
- Prefer `getByRole` + `name` for anything interactive.
- Use `exact` matching deliberately to avoid over-broad matches.
