/**
 * @jest-environment node
 *
 * Import / add tools must live on one hub page, not split across the
 * header dropdown, Recipes pills, Settings, and Dashboard.
 */
import fs from 'fs';
import path from 'path';

describe('add/import recipe hub', () => {
  const hub = fs.readFileSync(path.join(__dirname, 'AddRecipe.jsx'), 'utf8');
  const recipes = fs.readFileSync(path.join(__dirname, 'Recipes.jsx'), 'utf8');
  const layout = fs.readFileSync(path.join(__dirname, '../components/Layout.jsx'), 'utf8');
  const app = fs.readFileSync(path.join(__dirname, '../App.jsx'), 'utf8');
  const settings = fs.readFileSync(path.join(__dirname, 'Settings.jsx'), 'utf8');
  const dashboard = fs.readFileSync(path.join(__dirname, 'Dashboard.jsx'), 'utf8');
  const tonight = fs.readFileSync(path.join(__dirname, '../components/TonightSuggestions.jsx'), 'utf8');
  const pantry = fs.readFileSync(path.join(__dirname, 'Pantry.jsx'), 'utf8');
  const cookbooks = fs.readFileSync(path.join(__dirname, 'Cookbooks.jsx'), 'utf8');

  it('puts Mealime migrate first on the add hub', () => {
    const migrateAt = hub.indexOf('add-hub-migrate');
    const pasteAt = hub.indexOf('add-hub-paste');
    expect(migrateAt).toBeGreaterThan(-1);
    expect(migrateAt).toBeLessThan(pasteAt);
  });

  it('lists every import tool on /recipes/add', () => {
    expect(hub).toMatch(/data-testid="add-recipe-hub"/);
    expect(hub).toContain('/recipes/quick-add');
    expect(hub).toContain('/recipes/import');
    expect(hub).toContain('/recipes/import-batch');
    expect(hub).toContain('/recipes/migrate');
    expect(hub).toContain('/recipes/store-meal');
    expect(hub).toContain('/recipes/new');
    expect(hub).toContain('importRecipeArchive');
  });

  it('spells LARO as Local Archived Recipes Organised', () => {
    const acrostic = fs.readFileSync(
      path.join(__dirname, '../components/BrandAcrostic.jsx'),
      'utf8'
    );
    const en = fs.readFileSync(path.join(__dirname, '../locales/en.js'), 'utf8');
    expect(acrostic).toMatch(/brandAcrosticL/);
    expect(en).toMatch(/brandAcrosticL: 'Local'/);
    expect(en).toMatch(/brandAcrosticA: 'Archived'/);
    expect(en).toMatch(/brandAcrosticR: 'Recipes'/);
    expect(en).toMatch(/brandAcrosticO: 'Organised'/);
  });

  it('is registered as a route', () => {
    expect(app).toMatch(/path="\/recipes\/add"/);
    expect(app).toMatch(/AddRecipe/);
  });

  it('explains LARO in the app chrome', () => {
    const en = fs.readFileSync(path.join(__dirname, '../locales/en.js'), 'utf8');
    expect(layout).toMatch(/brandAcrosticLine/);
    expect(en).toMatch(/brandAcrosticLine: 'Local · Archived · Recipes · Organised'/);
  });

  it('header has no Add dropdown or Add button', () => {
    expect(layout).not.toMatch(/add-recipe-trigger/);
    expect(layout).not.toMatch(/add-recipe-quick/);
    expect(layout).not.toMatch(/navigate\('\/recipes\/add'\)/);
  });

  it('Recipes page has a single Add Recipe CTA to the hub', () => {
    expect(recipes).toMatch(/to="\/recipes\/add"/);
    expect(recipes).not.toMatch(/to="\/recipes\/import"/);
  });

  it('Settings no longer hosts the archive uploader', () => {
    expect(settings).not.toMatch(/handleImportFile/);
    expect(settings).toMatch(/\/recipes\/add/);
  });

  it('landing Mealime pill goes to migrate (login keeps next=)', () => {
    const landing = fs.readFileSync(path.join(__dirname, 'Landing.jsx'), 'utf8');
    const app = fs.readFileSync(path.join(__dirname, '../App.jsx'), 'utf8');
    expect(landing).toMatch(/data-testid="landing-mealime-migrate"/);
    expect(landing).toMatch(/data-testid="hero-self-host"/);
    expect(landing).toMatch(/data-testid="hero-mealime-migrate"/);
    expect(landing).toMatch(/headerCloudOptional/);
    expect(landing).toMatch(/sm:min-h-\[100svh\]/);
    expect(landing).toMatch(/overflow-x-hidden/);
    expect(landing).not.toMatch(/min-h-screen bg-background overflow-hidden/);
    expect(landing).toMatch(/to="\/recipes\/migrate"/);
    expect(landing).toMatch(/brand-origin/);
    expect(landing).toMatch(/brandAcrosticLine/);
    expect(app).toMatch(/next=\$\{encodeURIComponent/);
  });

  it('other add/import CTAs go to the hub', () => {
    expect(dashboard).toMatch(/to="\/recipes\/add"/);
    expect(dashboard).not.toMatch(/to="\/recipes\/import"/);
    expect(tonight).toMatch(/navigate\('\/recipes\/add'\)/);
    expect(tonight).not.toMatch(/navigate\('\/recipes\/new'\)/);
    expect(pantry).toMatch(/to="\/recipes\/add"/);
    expect(cookbooks).toMatch(/to="\/recipes\/add"/);
  });
});
