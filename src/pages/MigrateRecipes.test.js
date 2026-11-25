/**
 * @jest-environment node
 */
import fs from 'fs';
import path from 'path';

describe('closing-app migrate page', () => {
  const page = fs.readFileSync(path.join(__dirname, 'MigrateRecipes.jsx'), 'utf8');
  const hub = fs.readFileSync(path.join(__dirname, 'AddRecipe.jsx'), 'utf8');
  const app = fs.readFileSync(path.join(__dirname, '../App.jsx'), 'utf8');
  const api = fs.readFileSync(path.join(__dirname, '../lib/api.js'), 'utf8');

  it('is on the Add Recipe hub and routed', () => {
    expect(hub).toContain('/recipes/migrate');
    expect(hub).toMatch(/add-hub-migrate/);
    expect(app).toMatch(/path="\/recipes\/migrate"/);
  });

  it('calls the migrate API', () => {
    expect(api).toMatch(/\/import\/migrate/);
    expect(page).toMatch(/migrateClosingApps/);
    expect(page).toMatch(/migrate-paste/);
  });

  it('auto-continues leftover paste and can plan the week', () => {
    expect(page).toMatch(/remaining_text/);
    expect(page).toMatch(/planMigratedWeek/);
    expect(page).toMatch(/migrate-plan-week/);
    expect(api).toMatch(/\/import\/migrate\/plan-week/);
  });
});
