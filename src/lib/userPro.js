/** True when auth / me payload grants Laro Pro (matches Settings subscription fallbacks). */
export function userHasPro(user) {
  return Boolean(
    user?.is_pro || user?.is_owner || user?.subscription_active
  );
}
