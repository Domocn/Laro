/**
 * Debug Utilities for Mise Frontend
 *
 * Provides comprehensive debugging capabilities:
 * - Console logging with levels and colors
 * - API request/response logging
 * - State change logging
 * - Performance timing
 * - Error tracking
 *
 * Usage:
 *   import { debug, DebugLogger } from './debug';
 *
 *   // Simple logging
 *   debug.log('auth', 'User logged in', { userId: '123' });
 *   debug.error('api', 'Request failed', { status: 500 });
 *
 *   // Module-specific logger
 *   const logger = new DebugLogger('recipes');
 *   logger.info('Recipe loaded', { recipeId: '456' });
 */

// Check if debug mode is enabled
const isDebugMode = () => {
  // Check localStorage first
  const localSetting = localStorage.getItem('laro_debug_mode');
  if (localSetting !== null) {
    return localSetting === 'true';
  }
  // Default to enabled in development
  return process.env.NODE_ENV === 'development';
};

// Debug level settings
const DEBUG_LEVELS = {
  DEBUG: 0,
  INFO: 1,
  WARN: 2,
  ERROR: 3,
  OFF: 4,
};

// Get current debug level
const getDebugLevel = () => {
  const level = localStorage.getItem('laro_debug_level') || 'INFO';
  return DEBUG_LEVELS[level.toUpperCase()] || DEBUG_LEVELS.INFO;
};

// Color schemes for different modules
const MODULE_COLORS = {
  auth: '#4CAF50',
  api: '#2196F3',
  websocket: '#9C27B0',
  recipes: '#FF9800',
  mealPlans: '#00BCD4',
  shopping: '#E91E63',
  ai: '#673AB7',
  cache: '#795548',
  context: '#607D8B',
  performance: '#F44336',
  default: '#9E9E9E',
};

/**
 * Format a value for logging
 */
const formatValue = (value, maxLength = 200) => {
  if (value === null) return 'null';
  if (value === undefined) return 'undefined';

  try {
    const str = typeof value === 'object' ? JSON.stringify(value) : String(value);
    return str.length > maxLength ? str.substring(0, maxLength) + '...' : str;
  } catch {
    return '[Unable to stringify]';
  }
};

/**
 * Get styled console arguments
 */
const getStyledArgs = (module, level, message, data = null) => {
  const color = MODULE_COLORS[module] || MODULE_COLORS.default;
  const timestamp = new Date().toISOString().split('T')[1].split('.')[0];

  const baseStyle = `color: ${color}; font-weight: bold;`;
  const messageStyle = 'color: inherit;';
  const dataStyle = 'color: #666;';

  let args = [
    `%c[${timestamp}] %c[${module.toUpperCase()}] %c${level}: ${message}`,
    baseStyle,
    baseStyle,
    messageStyle,
  ];

  if (data !== null) {
    args[0] += ' %c%o';
    args.push(dataStyle, data);
  }

  return args;
};

/**
 * Core debug logging function
 */
const logMessage = (level, module, message, data = null) => {
  if (!isDebugMode()) return;
  if (DEBUG_LEVELS[level] < getDebugLevel()) return;

  const args = getStyledArgs(module, level, message, data);

  switch (level) {
    case 'DEBUG':
      console.debug(...args);
      break;
    case 'INFO':
      console.info(...args);
      break;
    case 'WARN':
      console.warn(...args);
      break;
    case 'ERROR':
      console.error(...args);
      break;
    default:
      console.log(...args);
  }
};

/**
 * Debug logging interface
 */
export const debug = {
  log: (module, message, data) => logMessage('DEBUG', module, message, data),
  info: (module, message, data) => logMessage('INFO', module, message, data),
  warn: (module, message, data) => logMessage('WARN', module, message, data),
  error: (module, message, data) => logMessage('ERROR', module, message, data),

  // Convenience methods for common modules
  auth: {
    log: (message, data) => logMessage('DEBUG', 'auth', message, data),
    info: (message, data) => logMessage('INFO', 'auth', message, data),
    warn: (message, data) => logMessage('WARN', 'auth', message, data),
    error: (message, data) => logMessage('ERROR', 'auth', message, data),
  },
  api: {
    log: (message, data) => logMessage('DEBUG', 'api', message, data),
    info: (message, data) => logMessage('INFO', 'api', message, data),
    warn: (message, data) => logMessage('WARN', 'api', message, data),
    error: (message, data) => logMessage('ERROR', 'api', message, data),
  },
  ws: {
    log: (message, data) => logMessage('DEBUG', 'websocket', message, data),
    info: (message, data) => logMessage('INFO', 'websocket', message, data),
    warn: (message, data) => logMessage('WARN', 'websocket', message, data),
    error: (message, data) => logMessage('ERROR', 'websocket', message, data),
  },
};

/**
 * Module-specific logger class
 */
export class DebugLogger {
  constructor(module) {
    this.module = module;
    this.context = {};
  }

  setContext(context) {
    this.context = { ...this.context, ...context };
  }

  clearContext() {
    this.context = {};
  }

  _logWithContext(level, message, data) {
    const fullData = data ? { ...this.context, ...data } : this.context;
    logMessage(level, this.module, message, Object.keys(fullData).length > 0 ? fullData : null);
  }

  debug(message, data) {
    this._logWithContext('DEBUG', message, data);
  }

  info(message, data) {
    this._logWithContext('INFO', message, data);
  }

  warn(message, data) {
    this._logWithContext('WARN', message, data);
  }

  error(message, data) {
    this._logWithContext('ERROR', message, data);
  }
}

/**
 * API Request/Response Logger
 *
 * Usage:
 *   logApiRequest('POST', '/api/recipes', { title: 'New Recipe' });
 *   logApiResponse('POST', '/api/recipes', 201, 45, { id: '123' });
 */
export const logApiRequest = (method, url, body = null, headers = null) => {
  if (!isDebugMode()) return;

  const data = { method, url };
  if (body) data.body = formatValue(body, 500);
  if (headers) data.headers = headers;

  debug.api.log(`REQUEST ${method} ${url}`, data);
};

export const logApiResponse = (method, url, status, durationMs, data = null, error = null) => {
  if (!isDebugMode()) return;

  const logData = {
    method,
    url,
    status,
    duration: `${durationMs.toFixed(2)}ms`,
  };

  if (data) logData.response = formatValue(data, 300);
  if (error) logData.error = error;

  if (status >= 500) {
    debug.api.error(`RESPONSE ${status}`, logData);
  } else if (status >= 400) {
    debug.api.warn(`RESPONSE ${status}`, logData);
  } else if (durationMs > 1000) {
    debug.api.warn(`RESPONSE ${status} (SLOW)`, logData);
  } else {
    debug.api.log(`RESPONSE ${status}`, logData);
  }
};

/**
 * WebSocket Event Logger
 */
export const logWsEvent = (event, connectionId = null, data = null) => {
  if (!isDebugMode()) return;

  const logData = { event };
  if (connectionId) logData.connectionId = connectionId;
  if (data) logData.data = formatValue(data, 200);

  debug.ws.log(`WS_EVENT: ${event}`, logData);
};

/**
 * State Change Logger
 *
 * Usage:
 *   logStateChange('AuthContext', 'user', null, { id: '123', name: 'John' });
 */
export const logStateChange = (context, key, oldValue, newValue) => {
  if (!isDebugMode()) return;

  debug.log('context', `STATE_CHANGE: ${context}.${key}`, {
    from: formatValue(oldValue, 100),
    to: formatValue(newValue, 100),
  });
};

/**
 * Performance Timer
 *
 * Usage:
 *   const timer = new PerformanceTimer('loadRecipes');
 *   await loadRecipes();
 *   timer.end(); // Logs: "loadRecipes completed in 45.23ms"
 */
export class PerformanceTimer {
  constructor(operation, module = 'performance') {
    this.operation = operation;
    this.module = module;
    this.startTime = performance.now();

    if (isDebugMode()) {
      debug.log(module, `TIMER_START: ${operation}`);
    }
  }

  checkpoint(label) {
    if (!isDebugMode()) return;

    const elapsed = performance.now() - this.startTime;
    debug.log(this.module, `TIMER_CHECKPOINT: ${this.operation} - ${label}`, {
      elapsed: `${elapsed.toFixed(2)}ms`,
    });
  }

  end(additionalData = null) {
    const elapsed = performance.now() - this.startTime;

    if (!isDebugMode()) return elapsed;

    const data = {
      duration: `${elapsed.toFixed(2)}ms`,
      ...additionalData,
    };

    if (elapsed > 1000) {
      debug.warn(this.module, `TIMER_END: ${this.operation} (SLOW)`, data);
    } else {
      debug.log(this.module, `TIMER_END: ${this.operation}`, data);
    }

    return elapsed;
  }
}

/**
 * Error Tracker
 *
 * Tracks and logs errors with context for debugging
 */
class ErrorTracker {
  constructor() {
    this.errors = [];
    this.maxErrors = 50;
  }

  track(error, context = {}) {
    const errorEntry = {
      timestamp: new Date().toISOString(),
      message: error.message || String(error),
      stack: error.stack,
      context,
    };

    this.errors.push(errorEntry);

    // Keep only last N errors
    if (this.errors.length > this.maxErrors) {
      this.errors = this.errors.slice(-this.maxErrors);
    }

    debug.error('error', `ERROR TRACKED: ${errorEntry.message}`, context);

    return errorEntry;
  }

  getRecent(count = 10) {
    return this.errors.slice(-count);
  }

  clear() {
    this.errors = [];
  }

  getSummary() {
    return {
      total: this.errors.length,
      recent: this.getRecent(5),
    };
  }
}

export const errorTracker = new ErrorTracker();

/**
 * Debug Stats Collector
 *
 * Collects statistics about API calls, WebSocket events, etc.
 */
class DebugStats {
  constructor() {
    this.apiCalls = [];
    this.wsEvents = [];
    this.stateChanges = [];
    this.startTime = Date.now();
  }

  recordApiCall(method, url, status, durationMs) {
    this.apiCalls.push({
      timestamp: Date.now(),
      method,
      url,
      status,
      duration: durationMs,
    });

    // Keep only last 100 calls
    if (this.apiCalls.length > 100) {
      this.apiCalls = this.apiCalls.slice(-100);
    }
  }

  recordWsEvent(event) {
    this.wsEvents.push({
      timestamp: Date.now(),
      event,
    });

    if (this.wsEvents.length > 100) {
      this.wsEvents = this.wsEvents.slice(-100);
    }
  }

  getSummary() {
    const totalApiCalls = this.apiCalls.length;
    const avgDuration =
      totalApiCalls > 0
        ? this.apiCalls.reduce((sum, call) => sum + call.duration, 0) / totalApiCalls
        : 0;
    const errorCalls = this.apiCalls.filter((c) => c.status >= 400).length;
    const slowCalls = this.apiCalls.filter((c) => c.duration > 1000).length;

    return {
      uptime: Date.now() - this.startTime,
      api: {
        totalCalls: totalApiCalls,
        avgDuration: avgDuration.toFixed(2),
        errorCount: errorCalls,
        slowCount: slowCalls,
      },
      websocket: {
        totalEvents: this.wsEvents.length,
      },
      errors: errorTracker.getSummary(),
    };
  }

  clear() {
    this.apiCalls = [];
    this.wsEvents = [];
    this.stateChanges = [];
  }
}

export const debugStats = new DebugStats();

/**
 * Debug Configuration
 */
export const debugConfig = {
  isEnabled: isDebugMode,
  getLevel: getDebugLevel,

  enable: () => {
    localStorage.setItem('laro_debug_mode', 'true');
    debug.info('debug', 'Debug mode enabled');
  },

  disable: () => {
    localStorage.setItem('laro_debug_mode', 'false');
    console.log('Debug mode disabled');
  },

  setLevel: (level) => {
    if (DEBUG_LEVELS[level.toUpperCase()] !== undefined) {
      localStorage.setItem('laro_debug_level', level.toUpperCase());
      debug.info('debug', `Debug level set to ${level}`);
    }
  },

  // Get all debug info
  getInfo: () => ({
    enabled: isDebugMode(),
    level: localStorage.getItem('laro_debug_level') || 'INFO',
    stats: debugStats.getSummary(),
  }),
};

/**
 * Create an axios interceptor for API debugging
 *
 * Usage:
 *   import api from './api';
 *   import { createApiDebugInterceptor } from './debug';
 *   createApiDebugInterceptor(api);
 */
export const createApiDebugInterceptor = (axiosInstance) => {
  // Request interceptor
  axiosInstance.interceptors.request.use(
    (config) => {
      // Store start time for duration calculation
      config.metadata = { startTime: performance.now() };

      logApiRequest(config.method?.toUpperCase(), config.url, config.data);

      return config;
    },
    (error) => {
      debug.api.error('Request setup failed', { error: error.message });
      return Promise.reject(error);
    }
  );

  // Response interceptor
  axiosInstance.interceptors.response.use(
    (response) => {
      const duration = performance.now() - (response.config.metadata?.startTime || 0);

      logApiResponse(
        response.config.method?.toUpperCase(),
        response.config.url,
        response.status,
        duration,
        response.data
      );

      debugStats.recordApiCall(
        response.config.method?.toUpperCase(),
        response.config.url,
        response.status,
        duration
      );

      return response;
    },
    (error) => {
      const duration = error.config
        ? performance.now() - (error.config.metadata?.startTime || 0)
        : 0;

      const status = error.response?.status || 0;

      logApiResponse(
        error.config?.method?.toUpperCase() || 'UNKNOWN',
        error.config?.url || 'unknown',
        status,
        duration,
        null,
        error.message
      );

      debugStats.recordApiCall(
        error.config?.method?.toUpperCase() || 'UNKNOWN',
        error.config?.url || 'unknown',
        status,
        duration
      );

      errorTracker.track(error, {
        url: error.config?.url,
        method: error.config?.method,
        status,
      });

      return Promise.reject(error);
    }
  );
};

// Export default debug object
export default debug;
