/**
 * @jest-environment node
 */
import { isQuietLegalPath } from './legalPaths';
import fs from 'fs';
import path from 'path';

describe('legal paths', () => {
  it('treats privacy and terms as quiet pages', () => {
    expect(isQuietLegalPath('/privacy-policy')).toBe(true);
    expect(isQuietLegalPath('/privacy-policy/')).toBe(true);
    expect(isQuietLegalPath('/terms')).toBe(true);
    expect(isQuietLegalPath('/recipes')).toBe(false);
  });

  it('nginx serves static privacy and terms without SPA fallback', () => {
    const nginx = fs.readFileSync(
      path.join(__dirname, '../../nginx.conf'),
      'utf8',
    );
    expect(nginx).toMatch(/location = \/privacy-policy/);
    expect(nginx).toMatch(/privacy-policy\.html/);
    expect(nginx).toMatch(/location = \/terms/);
    expect(nginx).toMatch(/terms\.html/);
    expect(nginx).toMatch(/location = \/\.well-known\/assetlinks\.json/);
  });

  it('static privacy policy is crawler-readable HTML', () => {
    const html = fs.readFileSync(
      path.join(__dirname, '../../public/privacy-policy.html'),
      'utf8',
    );
    expect(html).toMatch(/<h1[^>]*>Privacy Policy<\/h1>/);
    expect(html).toMatch(/Email address/);
    expect(html).toMatch(/Firebase/);
    expect(html).toMatch(/RevenueCat/);
    expect(html).toMatch(/OpenPanel/);
    expect(html).not.toMatch(/id="root"/);
  });

  it('static terms disclose free limits and auto-renewal', () => {
    const html = fs.readFileSync(
      path.join(__dirname, '../../public/terms.html'),
      'utf8',
    );
    expect(html).toMatch(/50 recipes/);
    expect(html).toMatch(/500 copies/);
    expect(html).toMatch(/3 lifetime AI uses/);
    expect(html).not.toMatch(/monthly cap on AI/);
    expect(html).toMatch(/auto-renew/i);
    expect(html).toMatch(/Google Play/);
    expect(html).toMatch(/export/i);
  });

  it('Caddy does not bounce legal paths into HashRouter', () => {
    const caddy = fs.readFileSync(
      path.join(__dirname, '../../Caddyfile'),
      'utf8',
    );
    expect(caddy).not.toMatch(/redir.*privacy-policy/);
    expect(caddy).not.toMatch(/@email_deep_link[^\n]*privacy/);
    expect(caddy).toMatch(/Do not bounce \/privacy-policy, \/terms, or \/\.well-known\/assetlinks\.json/);
  });

  it('sitemap lists path legal URLs, not hashes', () => {
    const sitemap = fs.readFileSync(
      path.join(__dirname, '../../public/sitemap.xml'),
      'utf8',
    );
    expect(sitemap).toMatch(/https:\/\/laro\.food\/privacy-policy/);
    expect(sitemap).toMatch(/https:\/\/laro\.food\/terms/);
    expect(sitemap).not.toMatch(/#\/privacy-policy/);
    expect(sitemap).not.toMatch(/#\/auth/);
  });

  it('index.html bounce list does not include legal pages', () => {
    const index = fs.readFileSync(
      path.join(__dirname, '../../index.html'),
      'utf8',
    );
    expect(index).toMatch(/\/verify-email/);
    expect(index).not.toMatch(/\/privacy-policy': true/);
    expect(index).not.toMatch(/\/terms': true/);
  });

  it('serves Digital Asset Links as JSON, not the SPA', () => {
    const json = fs.readFileSync(
      path.join(__dirname, '../../public/.well-known/assetlinks.json'),
      'utf8',
    );
    expect(JSON.parse(json)).toEqual([]);
  });
});
