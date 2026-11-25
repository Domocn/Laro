/**
 * @vitest-environment node
 *
 * Guards the API Tokens extraction out of the Settings page.
 *
 * The block owns its own list, form and one-time reveal state, so none of it
 * needs to live in the page. If the page stops passing `active`, tokens would
 * simply never load; if the component loses its error codes the client would
 * stop surfacing the backend detail.
 */
import fs from 'fs';
import path from 'path';

const settings = fs.readFileSync(
  path.join(__dirname, '../pages/Settings.jsx'),
  'utf8'
);
const section = fs.readFileSync(
  path.join(__dirname, '../components/settings/ApiTokensSection.jsx'),
  'utf8'
);
const en = fs.readFileSync(path.join(__dirname, '../locales/en.js'), 'utf8');

describe('ApiTokensSection extraction', () => {
  it('Settings renders the extracted component on the user tab', () => {
    expect(settings).toMatch(
      /import \{ ApiTokensSection \} from '\.\.\/components\/settings\/ApiTokensSection'/
    );
    expect(settings).toMatch(/<ApiTokensSection active=\{activeTab === 'user'\} \/>/);
  });

  it('Settings no longer carries the token state or handlers', () => {
    // The page must not keep a second copy of this state.
    expect(settings).not.toMatch(/apiTokensApi/);
    expect(settings).not.toMatch(/handleCreateToken/);
    expect(settings).not.toMatch(/loadApiTokens/);
    expect(settings).not.toMatch(/newlyCreatedToken/);
    expect(settings).not.toMatch(/const \[apiTokens, setApiTokens\]/);
  });

  it('the section owns its own API access', () => {
    expect(section).toMatch(/import \{ apiTokensApi \} from '\.\.\/\.\.\/lib\/api'/);
    for (const call of ['apiTokensApi.list()', 'apiTokensApi.create(', 'apiTokensApi.revoke(', 'apiTokensApi.delete(']) {
      expect(section).toContain(call);
    }
  });

  it('the section loads tokens only while the user tab is active', () => {
    expect(section).toMatch(/useEffect\(\(\) => \{/);
    expect(section).toMatch(/if \(active && apiTokens\.length === 0\)/);
  });

  it('keeps the client error codes the backend contract relies on', () => {
    expect(section).toContain('E-ST017'); // create
    expect(section).toContain('E-ST018'); // revoke
    expect(section).toContain('E-ST019'); // delete
  });

  it('still reveals a new token exactly once', () => {
    expect(section).toMatch(/setNewlyCreatedToken\(res\.data\.token\)/);
    expect(section).toMatch(/setNewlyCreatedToken\(null\)/);
  });

  it('every translation key it uses exists in en.js', () => {
    const keys = [...section.matchAll(/t\('([A-Za-z0-9_]+)'\)/g)].map((m) => m[1]);
    expect(keys.length).toBeGreaterThan(0);
    for (const key of keys) {
      expect(en, `missing locale key: ${key}`).toMatch(
        new RegExp(`^  ${key}:`, 'm')
      );
    }
  });
});
