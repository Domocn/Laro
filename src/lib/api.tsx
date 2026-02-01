import axios from 'axios';
import { createApiDebugInterceptor, debug } from './debug';

// Runtime backend URL - this placeholder gets replaced by docker-entrypoint.sh at container startup
// DO NOT CHANGE this string - it must match the placeholder in docker-entrypoint.sh
const RUNTIME_BACKEND_URL = '%REACT_APP_BACKEND_URL%';

// Get server URL - check localStorage first, then runtime env, then fallback to same-origin
// When using same-origin (empty string), requests go through nginx proxy to backend
const getServerUrl = () => {
  const savedUrl = localStorage.getItem('mise_server_url');
  if (savedUrl) {
    return savedUrl;
  }
  // Check if runtime placeholder was replaced (doesn't start with %)
  if (RUNTIME_BACKEND_URL && !RUNTIME_BACKEND_URL.startsWith('%')) {
    return RUNTIME_BACKEND_URL;
  }
  // Fallback to build-time env or empty (same-origin, uses nginx proxy)
  return process.env.REACT_APP_BACKEND_URL || '';
};

// Check if we're using same-origin mode (nginx proxy)
const isUsingProxy = () => {
  const url = getServerUrl();
  return !url || url.length === 0;
};

// Check if server is configured
// Returns true if explicit URL is set OR if using same-origin proxy mode
const isServerConfigured = () => {
  const url = getServerUrl();
  // If URL is set, server is configured
  if (url && url.length > 0) {
    return true;
  }
  // If using same-origin (proxy mode), server is always configured
  // This is determined by checking if we're running in a browser context
  // where the app was served (not file://)
  return typeof window !== 'undefined' && window.location.protocol !== 'file:';
};

// Use relative URL (no leading slash) for same-origin mode to support HA ingress
// With HA ingress, '/api/' would go to HA's API, but 'api/' goes through ingress
const getApiBaseUrl = () => {
  const serverUrl = getServerUrl();
  if (serverUrl) {
    // External server URL specified
    return serverUrl + '/api';
  }
  // Same-origin mode: use relative URL for HA ingress compatibility
  return 'api';
};

const api = axios.create({
  baseURL: getApiBaseUrl(),
});

// Add debug interceptor for API call logging
createApiDebugInterceptor(api);

debug.api.info('API client initialized', { baseURL: getApiBaseUrl() });

// Update baseURL when it might have changed
api.interceptors.request.use((config) => {
  // Check if server is configured
  if (!isServerConfigured()) {
    debug.api.warn('Server not configured, redirecting to config page');
    // Redirect to server config page (use hash for HashRouter compatibility)
    const currentHash = window.location.hash || '';
    if (!currentHash.includes('/server')) {
      window.location.hash = '#/server';
    }
    return Promise.reject(new Error('Server not configured. Please configure your server URL.'));
  }

  // Dynamically update baseURL in case it changed (e.g., user configured server URL)
  config.baseURL = getApiBaseUrl();

  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle auth errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      debug.auth.warn('Unauthorized response, clearing auth data');
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      // Use hash for HashRouter compatibility
      window.location.hash = '#/login';
    }
    return Promise.reject(error);
  }
);

// Auth
export const authApi = {
  register: (data) => api.post('/auth/register', data),
  login: (data) => api.post('/auth/login', data),
  logout: () => api.post('/auth/logout'),
  me: () => api.get('/auth/me'),
  updateProfile: (data) => api.put('/auth/me', data),
  deleteAccount: () => api.delete('/auth/me'),
};

// Households
export const householdApi = {
  create: (data) => api.post('/households', data),
  getMy: () => api.get('/households/me'),
  getMembers: () => api.get('/households/members'),
  invite: (email) => api.post('/households/invite', { email }),
  leave: () => api.post('/households/leave'),
  generateJoinCode: () => api.post('/households/join-code'),
  revokeJoinCode: () => api.delete('/households/join-code'),
  joinWithCode: (code) => api.post('/households/join', { join_code: code }),
};

// Recipes
export const recipeApi = {
  getAll: (params) => api.get('/recipes', { params }),
  getOne: (id) => api.get(`/recipes/${id}`),
  create: (data) => api.post('/recipes', data),
  update: (id, data) => api.put(`/recipes/${id}`, data),
  delete: (id) => api.delete(`/recipes/${id}`),
  uploadImage: (id, file) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post(`/recipes/${id}/image`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  toggleFavorite: (id) => api.post(`/recipes/${id}/favorite`),
  getScaled: (id, servings) => api.get(`/recipes/${id}/scaled`, { params: { servings } }),
  getPrint: (id) => api.get(`/recipes/${id}/print`),
};

// Favorites
export const favoritesApi = {
  getAll: () => api.get('/favorites'),
};

// AI
export const aiApi = {
  importUrl: (url) => api.post('/ai/import-url', { url }),
  importText: (text) => api.post('/ai/import-text', { text }),
  fridgeSearch: (ingredients, searchOnline = false) =>
    api.post('/ai/fridge-search', { ingredients, search_online: searchOnline }),
  autoMealPlan: (days = 7, preferences = '', excludeRecipes = []) =>
    api.post('/ai/auto-meal-plan', { days, preferences, exclude_recipes: excludeRecipes }),
};

// Meal Plans
export const mealPlanApi = {
  getAll: (params) => api.get('/meal-plans', { params }),
  create: (data) => api.post('/meal-plans', data),
  delete: (id) => api.delete(`/meal-plans/${id}`),
};

// Shopping Lists
export const shoppingListApi = {
  getAll: () => api.get('/shopping-lists'),
  getOne: (id) => api.get(`/shopping-lists/${id}`),
  create: (data) => api.post('/shopping-lists', data),
  update: (id, data) => api.put(`/shopping-lists/${id}`, data),
  delete: (id) => api.delete(`/shopping-lists/${id}`),
  fromRecipes: (recipeIds) => api.post('/shopping-lists/from-recipes', recipeIds),
  // Check item endpoint for real-time sync
  checkItem: (listId, itemIndex, checked) =>
    api.patch(`/shopping-lists/${listId}/items/${itemIndex}/check`, null, {
      params: { checked }
    }),
  // Receipt scanning
  scanReceipt: (listId, file, autoCheck = true) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post(`/shopping-lists/${listId}/scan-receipt`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      params: { auto_check: autoCheck }
    });
  },
  applyMatches: (listId, matches) =>
    api.post(`/shopping-lists/${listId}/apply-matches`, matches),
};

// Categories
export const categoryApi = {
  getAll: () => api.get('/categories'),
};

// Sharing
export const shareApi = {
  createLink: (recipeId) => api.post(`/recipes/${recipeId}/share`),
  getShared: (shareId) => api.get(`/shared/${shareId}`),
};

// Calendar
export const calendarApi = {
  exportIcal: (startDate, endDate) => 
    api.get('/calendar/ical', { params: { start_date: startDate, end_date: endDate }, responseType: 'blob' }),
};

// Import (legacy - use recipeImportApi instead)
export const legacyImportApi = {
  fromPlatform: (platform, data) => api.post('/import/platform', { platform, data }),
};

// Notifications
export const notificationApi = {
  subscribe: (subscription) => api.post('/notifications/subscribe', subscription),
  getSettings: () => api.get('/notifications/settings'),
  updateSettings: (settings) => api.put('/notifications/settings', settings),
};

// LLM Settings
export const llmApi = {
  getSettings: () => api.get('/settings/llm'),
  updateSettings: (settings) => api.put('/settings/llm', settings),
  testConnection: (settings) => api.post('/settings/llm/test', settings),
};

// Custom AI Prompts
export const promptsApi = {
  get: () => api.get('/prompts'),
  update: (prompts) => api.put('/prompts', prompts),
  reset: () => api.delete('/prompts'),
};

// Cooking (Tonight suggestions, Cook Mode, Feedback)
export const cookingApi = {
  getTonightSuggestions: () => api.get('/cooking/tonight'),
  startSession: (recipeId) => api.post('/cooking/session', { recipe_id: recipeId }),
  completeSession: (sessionId, feedback) => api.post(`/cooking/session/${sessionId}/complete`, { feedback }),
  submitFeedback: (recipeId, feedback) => api.post('/cooking/feedback', { recipe_id: recipeId, feedback }),
  getStats: () => api.get('/cooking/stats'),
};

// Server Config
export const configApi = {
  getConfig: () => api.get('/config'),
  healthCheck: () => api.get('/health'),
  wsStatus: () => api.get('/ws/status'),
};

// Helper function to get base URL for WebSocket connections
// Returns empty string when using same-origin proxy mode
export const getBaseURL = () => getServerUrl();

// Export proxy check for components that need to know
export { isUsingProxy };

// Admin APIs
export const adminApi = {
  // User Management
  listUsers: (params) => api.get('/admin/users', { params }),
  getUser: (userId) => api.get(`/admin/users/${userId}`),
  updateUserRole: (userId, role) => api.put(`/admin/users/${userId}/role`, { role }),
  updateUserStatus: (userId, status) => api.put(`/admin/users/${userId}/status`, { status }),
  resetUserPassword: (userId, newPassword) => api.post(`/admin/users/${userId}/reset-password`, { new_password: newPassword }),
  deleteUser: (userId, permanent = false) => api.delete(`/admin/users/${userId}`, { params: { permanent } }),
  
  // User Data Export (GDPR)
  exportUserData: (userId) => api.get(`/admin/users/${userId}/export`),
  downloadUserData: (userId) => `${getApiBaseUrl()}/admin/users/${userId}/export/download`,
  
  // System Settings
  getSettings: () => api.get('/admin/settings'),
  updateSettings: (settings) => api.put('/admin/settings', settings),
  
  // Invite Codes
  listInviteCodes: () => api.get('/admin/invite-codes'),
  createInviteCode: (data) => api.post('/admin/invite-codes', data),
  deleteInviteCode: (codeId) => api.delete(`/admin/invite-codes/${codeId}`),
  
  // IP Access Rules
  getIPRules: () => api.get('/admin/ip-rules'),
  addIPAllowlist: (ip, description) => api.post('/admin/ip-rules/allowlist', { ip_pattern: ip, description }),
  addIPBlocklist: (ip, description) => api.post('/admin/ip-rules/blocklist', { ip_pattern: ip, description }),
  removeIPAllowlist: (ruleId) => api.delete(`/admin/ip-rules/allowlist/${ruleId}`),
  removeIPBlocklist: (ruleId) => api.delete(`/admin/ip-rules/blocklist/${ruleId}`),
  
  // Audit Logs
  getAuditLogs: (params) => api.get('/admin/audit-logs', { params }),
  
  // System Health
  getSystemHealth: () => api.get('/admin/system/health'),
  
  // Backups
  createBackup: () => api.post('/admin/backup'),
  listBackups: () => api.get('/admin/backups'),
  getBackupSettings: () => api.get('/admin/backup-settings'),
  updateBackupSettings: (enabled, intervalHours, maxBackups) => 
    api.put(`/admin/backup-settings?enabled=${enabled}&interval_hours=${intervalHours}&max_backups=${maxBackups}`),
};

// Security APIs
export const securityApi = {
  // Password Reset
  requestPasswordReset: (email) => api.post('/security/password-reset/request', { email }),
  confirmPasswordReset: (token, newPassword) => api.post('/security/password-reset/confirm', { token, new_password: newPassword }),
  changePassword: (currentPassword, newPassword) => api.post('/security/password/change', { current_password: currentPassword, new_password: newPassword }),
  
  // 2FA
  setup2FA: () => api.post('/security/2fa/setup'),
  verify2FA: (code) => api.post('/security/2fa/verify', { code }),
  disable2FA: (password, code) => api.post('/security/2fa/disable', { password, code }),
  get2FAStatus: () => api.get('/security/2fa/status'),
  regenerateBackupCodes: (code) => api.post('/security/2fa/regenerate-backup-codes', { code }),
  
  // Sessions
  getSessions: () => api.get('/security/sessions'),
  revokeSession: (sessionId) => api.delete(`/security/sessions/${sessionId}`),
  revokeAllSessions: (keepCurrent = true) => api.delete('/security/sessions', { params: { keep_current: keepCurrent } }),
  
  // Login Attempts
  getLoginAttempts: () => api.get('/security/login-attempts'),
};

// OAuth APIs
export const oauthApi = {
  getStatus: () => api.get('/oauth/status'),
  getGoogleAuthUrl: () => api.get('/oauth/google/auth-url'),
  googleCallback: (code, state) => api.post('/oauth/google/callback', { code, state }),
  getGitHubAuthUrl: () => api.get('/oauth/github/auth-url'),
  githubCallback: (code, state) => api.post('/oauth/github/callback', { code, state }),
  getLinkedAccounts: () => api.get('/oauth/linked-accounts'),
  unlinkAccount: (provider) => api.delete(`/oauth/linked-accounts/${provider}`),
};

// Roles APIs
export const rolesApi = {
  list: () => api.get('/roles'),
  get: (roleId) => api.get(`/roles/${roleId}`),
  create: (data) => api.post('/roles', data),
  update: (roleId, data) => api.put(`/roles/${roleId}`, data),
  delete: (roleId) => api.delete(`/roles/${roleId}`),
  assign: (userId, roleId) => api.post('/roles/assign', { user_id: userId, role_id: roleId }),
  getDefaultPermissions: () => api.get('/roles/permissions/default'),
};

// Trusted Devices APIs
export const trustedDevicesApi = {
  list: () => api.get('/trusted-devices'),
  trustDevice: (deviceName) => api.post('/trusted-devices', { device_name: deviceName }),
  revoke: (deviceId) => api.delete(`/trusted-devices/${deviceId}`),
  revokeAll: () => api.delete('/trusted-devices'),
  check: (trustToken) => api.get('/trusted-devices/check', { params: { trust_token: trustToken } }),
};

// Recipe Versions APIs
export const recipeVersionsApi = {
  list: (recipeId) => api.get(`/recipes/${recipeId}/versions`),
  get: (recipeId, version) => api.get(`/recipes/${recipeId}/versions/${version}`),
  restore: (recipeId, version) => api.post(`/recipes/${recipeId}/versions/${version}/restore`),
  compare: (recipeId, versionA, versionB) => api.post(`/recipes/${recipeId}/versions/compare`, { version_a: versionA, version_b: versionB }),
};

// Nutrition APIs
export const nutritionApi = {
  calculate: (ingredients, servings = 1) => api.post('/nutrition/calculate', { ingredients, servings }),
  getRecipeNutrition: (recipeId) => api.get(`/nutrition/recipe/${recipeId}`),
  saveRecipeNutrition: (recipeId) => api.post(`/nutrition/recipe/${recipeId}/save`),
  listIngredients: () => api.get('/nutrition/ingredients'),
  getIngredient: (name) => api.get(`/nutrition/ingredient/${name}`),
  addCustomIngredient: (data) => api.post('/nutrition/custom-ingredient', data),
};

// Recipe Import APIs
export const importApi = {
  getPlatforms: () => api.get('/import/platforms'),
  importFromUrl: (url) => api.post('/import/url', { url }),
  bulkImport: (urls) => api.post('/import/bulk', { urls }),
  importFromText: (text, title) => api.post('/import/text', { text, title }),
};

// Voice Cooking APIs
export const voiceApi = {
  getLanguages: () => api.get('/voice/languages'),
  getCommands: () => api.get('/voice/commands'),
  prepareTTS: (text, language, rate) => api.post('/voice/tts/prepare', { text, language, rate }),
  processCommand: (command, recipeId, currentStep) => api.post('/voice/command', { command, recipe_id: recipeId, current_step: currentStep }),
  getSettings: () => api.get('/voice/settings'),
  updateSettings: (settings) => api.put('/voice/settings', settings),
  prepareRecipe: (recipeId) => api.post(`/voice/recipe/${recipeId}/prepare-steps`),
};

// Cost Tracking APIs
export const costApi = {
  getPrices: () => api.get('/costs/prices'),
  addPrice: (data) => api.post('/costs/prices', data),
  deletePrice: (priceId) => api.delete(`/costs/prices/${priceId}`),
  getRecipeCost: (recipeId) => api.get(`/costs/recipe/${recipeId}`),
  saveRecipeCost: (recipeId) => api.post(`/costs/recipe/${recipeId}/save`),
  getSummary: () => api.get('/costs/summary'),
  getBudgetFriendly: (maxCost) => api.get('/costs/budget', { params: { max_cost: maxCost } }),
};

// Reviews APIs
export const reviewsApi = {
  getTags: () => api.get('/reviews/tags'),
  create: (data) => api.post('/reviews', data),
  getForRecipe: (recipeId) => api.get(`/reviews/recipe/${recipeId}`),
  getUserReviews: () => api.get('/reviews/user'),
  get: (reviewId) => api.get(`/reviews/${reviewId}`),
  update: (reviewId, data) => api.put(`/reviews/${reviewId}`, data),
  delete: (reviewId) => api.delete(`/reviews/${reviewId}`),
  markHelpful: (reviewId) => api.post(`/reviews/${reviewId}/helpful`),
  getTopRated: (limit = 10) => api.get('/reviews/top-rated', { params: { limit } }),
  getWouldMakeAgain: () => api.get('/reviews/would-make-again'),
};

// Recipe Sharing APIs
export const sharingApi = {
  create: (data) => api.post('/share/create', data),
  getMyLinks: () => api.get('/share/my-links'),
  getSharedRecipe: (shareCode) => api.get(`/share/recipe/${shareCode}`),
  revoke: (linkId) => api.delete(`/share/${linkId}`),
  getStats: (linkId) => api.get(`/share/stats/${linkId}`),
  getSettings: () => api.get('/share/settings'),
};

// API Tokens APIs
export const apiTokensApi = {
  list: () => api.get('/api-tokens'),
  create: (data) => api.post('/api-tokens', data),
  delete: (tokenId) => api.delete(`/api-tokens/${tokenId}`),
  revoke: (tokenId) => api.post(`/api-tokens/${tokenId}/revoke`),
};

export default api;
