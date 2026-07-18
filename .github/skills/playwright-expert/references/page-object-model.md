# Page Object Model (POM)

POM separates test logic from UI structure. When the markup changes, you edit one Page Object instead of every test.

## Basic Page Object

```ts
// pages/LoginPage.ts
import { type Page, type Locator } from '@playwright/test';

export class LoginPage {
  readonly page: Page;
  readonly emailInput: Locator;
  readonly passwordInput: Locator;
  readonly submitButton: Locator;
  readonly errorMessage: Locator;

  constructor(page: Page) {
    this.page = page;
    this.emailInput = page.getByLabel('Email address');
    this.passwordInput = page.getByLabel('Password');
    this.submitButton = page.getByRole('button', { name: 'Sign in' });
    this.errorMessage = page.getByRole('alert');
  }

  async goto() {
    await this.page.goto('/login');
  }

  async login(email: string, password: string) {
    await this.emailInput.fill(email);
    await this.passwordInput.fill(password);
    await this.submitButton.click();
  }
}
```

## Test File Using the Page Object

```ts
// tests/login.spec.ts
import { test, expect } from '@playwright/test';
import { LoginPage } from '../pages/LoginPage';

test.describe('Login', () => {
  let loginPage: LoginPage;

  test.beforeEach(async ({ page }) => {
    loginPage = new LoginPage(page);
    await loginPage.goto();
  });

  test('successful login redirects to dashboard', async ({ page }) => {
    await loginPage.login('user@example.com', 'correct-password');
    await expect(page).toHaveURL('/dashboard');
  });

  test('invalid credentials shows error', async () => {
    await loginPage.login('user@example.com', 'wrong-password');
    await expect(loginPage.errorMessage).toBeVisible();
    await expect(loginPage.errorMessage).toContainText('Invalid credentials');
  });
});
```

## Composition (Page Objects referencing each other)

```ts
export class DashboardPage {
  constructor(private page: Page) {}
  async openSettings() {
    await this.page.getByRole('link', { name: 'Settings' }).click();
    return new SettingsPage(this.page);
  }
}
```

## Fixtures

Use fixtures to set up reusable, isolated state. Fixtures are scoped and torn down automatically.

```ts
// fixtures.ts
import { test as base } from '@playwright/test';
import { LoginPage } from '../pages/LoginPage';

export const test = base.extend<{ loginPage: LoginPage }>({
  loginPage: async ({ page }, use) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto();
    await use(loginPage);
  },
});

export { expect } from '@playwright/test';
```

```ts
// usage
import { test, expect } from './fixtures';

test('uses fixture', async ({ loginPage }) => {
  await loginPage.login('user@example.com', 'pw');
  await expect(loginPage.errorMessage).toBeVisible();
});
```

## POM Rules

- Page Objects hold **locators and actions**, not assertions. Assert in tests.
- Keep navigation (`goto`) in the Page Object.
- Compose pages by returning new Page Objects from actions.
- One Page Object per page/component; avoid giant "god" objects.
- Never share state across tests via module-level variables — use fixtures.
