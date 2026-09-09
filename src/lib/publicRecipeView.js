/**
 * Public shared-recipe routes should stay quiet — no cookie banner, PWA
 * install prompt, onboarding, or tour until the viewer clicks a Join CTA
 * and leaves this view.
 */
export function isPublicRecipeViewPath(pathname = '') {
  const path = String(pathname || '');
  return (
    path.startsWith('/recipe/') ||
    path.startsWith('/r/') ||
    path.startsWith('/shared/')
  );
}
