import { test, expect } from '@playwright/test';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const e2eDir = path.dirname(fileURLToPath(import.meta.url));
const statePath = path.join(e2eDir, '../.auth/user.json');

function authFromStorageState(): { token: string; user: Record<string, unknown> } {
  const state = JSON.parse(fs.readFileSync(statePath, 'utf8')) as {
    origins?: Array<{ localStorage?: Array<{ name: string; value: string }> }>;
  };
  const store = state.origins?.[0]?.localStorage ?? [];
  const token = store.find((x) => x.name === 'token')?.value;
  const userRaw = store.find((x) => x.name === 'user')?.value;
  if (!token || !userRaw) {
    throw new Error('E2E storage state missing token/user — run full playwright once with E2E_FORCE_AUTH=1');
  }
  return { token, user: JSON.parse(userRaw) as Record<string, unknown> };
}

test.describe('Public', () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test('landing page loads', async ({ page }) => {
    await page.goto('/#/');
    await expect(page.locator('body')).toBeVisible();
    await expect(page.getByRole('link', { name: /log in|sign in/i }).first()).toBeVisible();
  });

  test('login form renders', async ({ page }) => {
    await page.goto('/#/login');
    await expect(page.getByTestId('login-email')).toBeVisible();
    await expect(page.getByTestId('login-password')).toBeVisible();
    await expect(page.getByTestId('login-submit')).toBeVisible();
  });
});

test.describe('Authenticated smoke', () => {
  test.beforeEach(async ({ context }) => {
    const apiUrl = process.env.PLAYWRIGHT_API_URL || 'http://127.0.0.1:8001';
    await context.addInitScript((serverUrl) => {
      if (!localStorage.getItem('laro_server_url')) {
        localStorage.setItem('laro_server_url', serverUrl);
      }
    }, apiUrl);
  });

  test('dashboard', async ({ page }) => {
    await page.goto('/#/dashboard');
    await expect(page.getByTestId('dashboard')).toBeVisible();
  });

  test('recipes list', async ({ page }) => {
    await page.goto('/#/recipes');
    await expect(page.getByTestId('recipes-page')).toBeVisible();
    await expect(page.getByTestId('nav-recipes')).toBeVisible();
  });

  test('meal planner', async ({ page }) => {
    await page.goto('/#/meal-planner');
    await expect(page.getByTestId('nav-meal-plan')).toBeVisible();
  });

  test('shopping lists', async ({ page }) => {
    await page.goto('/#/shopping');
    await expect(page.getByTestId('nav-shopping')).toBeVisible();
  });

  test('user preferences', async ({ page }) => {
    await page.goto('/#/settings/preferences');
    await expect(page.getByText(/accessibility|appearance|cooking/i).first()).toBeVisible();
  });

  test('support', async ({ page }) => {
    await page.goto('/#/support');
    await expect(page.getByText(/ticket|support|problem/i).first()).toBeVisible();
  });

  test('settings hub', async ({ page }) => {
    await page.goto('/#/settings');
    await expect(page.locator('body')).toContainText(/account|profile|settings/i);
  });
});

test.describe('Recipe chat', () => {
  test.beforeEach(async ({ context }) => {
    const apiUrl = process.env.PLAYWRIGHT_API_URL || 'http://127.0.0.1:8001';
    await context.addInitScript((serverUrl) => {
      if (!localStorage.getItem('laro_server_url')) {
        localStorage.setItem('laro_server_url', serverUrl);
      }
    }, apiUrl);
  });

  test('report problem from chat menu without sending a message', async ({ page, request }) => {
    const apiUrl = (process.env.PLAYWRIGHT_API_URL || 'http://127.0.0.1:8001').replace(/\/$/, '');
    const loginBody = authFromStorageState();

    const recipesRes = await request.get(`${apiUrl}/api/v1/recipes`, {
      headers: { Authorization: `Bearer ${loginBody.token}` },
    });
    expect(recipesRes.ok()).toBeTruthy();
    const recipes = (await recipesRes.json()) as Array<{ id: string }>;
    expect(recipes.length).toBeGreaterThan(0);

    await page.addInitScript((auth) => {
      localStorage.setItem('token', auth.token);
      localStorage.setItem('user', JSON.stringify(auth.user));
    }, loginBody);
    await page.goto(`/#/recipes/${recipes[0].id}`);
    await expect(page.getByTestId('recipe-detail')).toBeVisible({ timeout: 15_000 });

    await expect(page.getByTestId('chat-button')).toBeVisible({ timeout: 15_000 });
    await page.getByTestId('chat-button').click();
    await expect(page.getByTestId('chat-modal')).toBeVisible();

    await page.getByRole('button', { name: 'More chat actions' }).click();
    const reportItem = page.getByRole('menuitem', { name: /report a problem/i });
    await expect(reportItem).toBeEnabled();
    await reportItem.click();

    await expect(
      page.getByRole('region', { name: /notifications/i }).getByText(/bug reported|reported/i)
    ).toBeVisible({ timeout: 15_000 });
  });
});
