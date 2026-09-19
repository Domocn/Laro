import { chromium, type FullConfig } from '@playwright/test';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const authDir = path.join(__dirname, '.auth');
const statePath = path.join(authDir, 'user.json');
const credPath = path.join(authDir, 'credentials.json');

const apiBase = () =>
  (process.env.PLAYWRIGHT_API_URL || 'http://127.0.0.1:8001').replace(/\/$/, '');

async function registerOrLogin(
  email: string,
  password: string,
  name: string
): Promise<{ token: string; user: Record<string, unknown> }> {
  const registerRes = await fetch(`${apiBase()}/api/v1/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email,
      password,
      name,
      country: 'GB',
      language: 'en-GB',
    }),
  });

  if (registerRes.ok) {
    const body = await registerRes.json();
    if (body.token && body.user) {
      return { token: body.token as string, user: body.user as Record<string, unknown> };
    }
    if (body.requires_verification) {
      throw new Error(
        'E2E registration requires email verification — use a backend with EMAIL disabled or set E2E_EMAIL/E2E_PASSWORD.'
      );
    }
  }

  const loginRes = await fetch(`${apiBase()}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!loginRes.ok) {
    const detail = await loginRes.text();
    throw new Error(`E2E auth failed (${loginRes.status}): ${detail}`);
  }
  const loginBody = await loginRes.json();
  if (!loginBody.token || !loginBody.user) {
    throw new Error('Login succeeded but token/user missing');
  }
  return { token: loginBody.token as string, user: loginBody.user as Record<string, unknown> };
}

function tokenFromStorageState(): string | null {
  if (!fs.existsSync(statePath)) return null;
  const state = JSON.parse(fs.readFileSync(statePath, 'utf8')) as {
    origins?: Array<{ localStorage?: Array<{ name: string; value: string }> }>;
  };
  for (const origin of state.origins || []) {
    const entry = origin.localStorage?.find((x) => x.name === 'token');
    if (entry?.value) return entry.value;
  }
  return null;
}

async function ensureSeededRecipe(token: string) {
  const seedTitle = 'E2E Playwright Soup';
  const listRes = await fetch(`${apiBase()}/api/v1/recipes`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!listRes.ok) {
    return;
  }
  const existing = (await listRes.json()) as Array<{ title?: string }>;
  if (existing.some((r) => r.title === seedTitle)) {
    return;
  }
  const recipeRes = await fetch(`${apiBase()}/api/v1/recipes`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      title: seedTitle,
      description: 'Seeded for smoke tests',
      ingredients: [{ name: 'water', amount: '1', unit: 'cup' }],
      instructions: ['Simmer water.', 'Serve.'],
      category: 'Other',
    }),
  });
  if (!recipeRes.ok) {
    const detail = await recipeRes.text();
    throw new Error(`E2E recipe seed failed (${recipeRes.status}): ${detail}`);
  }
}

export default async function globalSetup(config: FullConfig) {
  fs.mkdirSync(authDir, { recursive: true });

  let email = process.env.E2E_EMAIL;
  let password = process.env.E2E_PASSWORD;
  let name = process.env.E2E_NAME || 'E2E Smoke';
  if (!email && fs.existsSync(credPath)) {
    const saved = JSON.parse(fs.readFileSync(credPath, 'utf8')) as {
      email?: string;
      password?: string;
      name?: string;
    };
    email = saved.email;
    password = saved.password;
    name = saved.name || name;
  }
  email = email || `e2e-${Date.now()}@example.com`;
  password = password || 'E2eSmokeTest1!';

  const reuseSession =
    fs.existsSync(statePath) && process.env.E2E_FORCE_AUTH !== '1';

  if (reuseSession) {
    const cachedToken = tokenFromStorageState();
    if (cachedToken) {
      await ensureSeededRecipe(cachedToken);
      return;
    }
  }

  const { token } = await registerOrLogin(email, password, name);
  fs.writeFileSync(credPath, JSON.stringify({ email, password, name }, null, 2));

  await ensureSeededRecipe(token);
  if (reuseSession) {
    return;
  }

  const baseURL = config.projects[0].use.baseURL as string;
  const apiUrl = (process.env.PLAYWRIGHT_API_URL || 'http://127.0.0.1:8001').replace(/\/$/, '');
  const browser = await chromium.launch();
  const context = await browser.newContext();
  await context.addInitScript((serverUrl) => {
    localStorage.setItem('laro_server_url', serverUrl);
  }, apiUrl);
  const page = await context.newPage();

  await page.goto(`${baseURL}/#/login`);

  const acceptCookies = page.getByRole('button', { name: /^accept$/i });
  if (await acceptCookies.isVisible().catch(() => false)) {
    await acceptCookies.click();
  }

  await page.getByTestId('login-email').fill(email);
  await page.getByTestId('login-password').fill(password);
  await page.getByTestId('login-submit').click();

  await page.waitForURL(/#\/dashboard/, { timeout: 90_000 });
  await page.waitForSelector('[data-testid="dashboard"]', { timeout: 30_000 });

  await context.storageState({ path: statePath });
  await browser.close();
}
