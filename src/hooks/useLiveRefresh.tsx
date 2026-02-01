/**
 * Live Refresh Hook - WebSocket connection for real-time updates
 * Provides live refresh functionality for shopping lists, recipes, meal plans, etc.
 */
import { useState, useEffect, useCallback, useRef } from 'react';
import { debug, logWsEvent, debugStats } from '../lib/debug';

// Event types matching backend
export const EventType = {
  // Shopping list events
  SHOPPING_LIST_CREATED: 'shopping_list:created',
  SHOPPING_LIST_UPDATED: 'shopping_list:updated',
  SHOPPING_LIST_DELETED: 'shopping_list:deleted',
  SHOPPING_LIST_ITEM_CHECKED: 'shopping_list:item_checked',

  // Recipe events
  RECIPE_CREATED: 'recipe:created',
  RECIPE_UPDATED: 'recipe:updated',
  RECIPE_DELETED: 'recipe:deleted',
  RECIPE_FAVORITED: 'recipe:favorited',

  // Meal plan events
  MEAL_PLAN_CREATED: 'meal_plan:created',
  MEAL_PLAN_UPDATED: 'meal_plan:updated',
  MEAL_PLAN_DELETED: 'meal_plan:deleted',

  // Household events
  HOUSEHOLD_MEMBER_JOINED: 'household:member_joined',
  HOUSEHOLD_MEMBER_LEFT: 'household:member_left',
  HOUSEHOLD_UPDATED: 'household:updated',

  // Cook session events
  COOK_SESSION_STARTED: 'cook_session:started',
  COOK_SESSION_COMPLETED: 'cook_session:completed',

  // General events
  DATA_SYNC: 'data:sync',
  PING: 'ping',
  PONG: 'pong',
};

// Get WebSocket URL from localStorage or environment
// When using same-origin mode (nginx proxy), construct URL from current page location
// Supports HA ingress by using the current pathname as base
const getWebSocketUrl = () => {
  const savedUrl = localStorage.getItem('mise_server_url');
  const baseUrl = savedUrl || process.env.REACT_APP_BACKEND_URL || '';

  // If no explicit URL configured, use same-origin (nginx proxy mode)
  if (!baseUrl) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    // Get the base path (for HA ingress support)
    // E.g., /api/hassio_ingress/{token}/ -> /api/hassio_ingress/{token}/ws
    let basePath = window.location.pathname;
    // Remove trailing index.html or similar if present
    basePath = basePath.replace(/\/index\.html$/, '/').replace(/\/$/, '');
    // Handle hash router - pathname might just be /
    // In that case, we use empty base path
    if (basePath === '' || basePath === '/') {
      basePath = '';
    }
    return `${protocol}//${window.location.host}${basePath}/ws`;
  }

  // Convert HTTP URL to WebSocket URL
  const wsUrl = baseUrl.replace(/^http/, 'ws');
  return wsUrl + '/ws';
};

/**
 * Hook for managing WebSocket connection and live refresh
 * @param {Object} options - Configuration options
 * @param {boolean} options.autoConnect - Whether to connect automatically (default: true)
 * @param {number} options.reconnectInterval - Time in ms between reconnection attempts (default: 3000)
 * @param {number} options.maxReconnectAttempts - Maximum reconnection attempts (default: 10)
 * @returns {Object} WebSocket state and methods
 */
export function useLiveRefresh(options = {}) {
  const {
    autoConnect = true,
    reconnectInterval = 3000,
    maxReconnectAttempts = 10,
  } = options;

  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState(null);
  const [connectionError, setConnectionError] = useState(null);

  const wsRef = useRef(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef(null);
  const listenersRef = useRef(new Map());
  const pingIntervalRef = useRef(null);

  // Add event listener
  const addEventListener = useCallback((eventType, callback) => {
    if (!listenersRef.current.has(eventType)) {
      listenersRef.current.set(eventType, new Set());
    }
    listenersRef.current.get(eventType).add(callback);

    // Return cleanup function
    return () => {
      listenersRef.current.get(eventType)?.delete(callback);
    };
  }, []);

  // Remove event listener
  const removeEventListener = useCallback((eventType, callback) => {
    listenersRef.current.get(eventType)?.delete(callback);
  }, []);

  // Notify listeners
  const notifyListeners = useCallback((eventType, data) => {
    const listeners = listenersRef.current.get(eventType);
    if (listeners) {
      listeners.forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          console.error('LiveRefresh listener error:', error);
        }
      });
    }
  }, []);

  // Send message through WebSocket
  const send = useCallback((message) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    }
  }, []);

  // Connect to WebSocket
  const connect = useCallback(() => {
    const token = localStorage.getItem('token');
    const wsUrl = getWebSocketUrl();

    if (!token || !wsUrl) {
      setConnectionError('No token or server URL configured');
      return;
    }

    // Close existing connection
    if (wsRef.current) {
      wsRef.current.close();
    }

    try {
      debug.ws.info('Connecting to WebSocket', { url: wsUrl.replace(/token=.*/, 'token=***') });
      const ws = new WebSocket(`${wsUrl}?token=${token}`);

      ws.onopen = () => {
        debug.ws.info('WebSocket connected');
        logWsEvent('CONNECTED');
        console.log('LiveRefresh: Connected');
        setIsConnected(true);
        setConnectionError(null);
        reconnectAttemptsRef.current = 0;

        // Start ping interval to keep connection alive
        pingIntervalRef.current = setInterval(() => {
          send({ type: 'ping', timestamp: Date.now() });
        }, 30000);
      };

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          setLastMessage(message);

          logWsEvent('MESSAGE', null, { type: message.type });
          debugStats.recordWsEvent(message.type);

          // Notify listeners for this event type
          notifyListeners(message.type, message.data);

          // Also notify 'all' listeners
          notifyListeners('all', message);
        } catch (error) {
          debug.ws.error('Failed to parse message', { error: error.message });
          console.error('LiveRefresh: Failed to parse message:', error);
        }
      };

      ws.onerror = (error) => {
        debug.ws.error('WebSocket error', { error: error.message || 'Unknown error' });
        logWsEvent('ERROR', null, { error: 'Connection error' });
        console.error('LiveRefresh: WebSocket error:', error);
        setConnectionError('Connection error');
      };

      ws.onclose = (event) => {
        debug.ws.info('WebSocket disconnected', { code: event.code, reason: event.reason });
        logWsEvent('DISCONNECTED', null, { code: event.code, reason: event.reason });
        console.log('LiveRefresh: Disconnected', event.code, event.reason);
        setIsConnected(false);

        // Clear ping interval
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
          pingIntervalRef.current = null;
        }

        // Attempt reconnection if not closed intentionally
        if (event.code !== 1000 && event.code !== 4001) {
          if (reconnectAttemptsRef.current < maxReconnectAttempts) {
            reconnectAttemptsRef.current++;
            debug.ws.info('Scheduling reconnection', {
              attempt: reconnectAttemptsRef.current,
              maxAttempts: maxReconnectAttempts,
              delayMs: reconnectInterval
            });
            console.log(`LiveRefresh: Reconnecting in ${reconnectInterval}ms (attempt ${reconnectAttemptsRef.current})`);

            reconnectTimeoutRef.current = setTimeout(() => {
              connect();
            }, reconnectInterval);
          } else {
            debug.ws.error('Max reconnection attempts reached');
            setConnectionError('Max reconnection attempts reached');
          }
        }
      };

      wsRef.current = ws;
    } catch (error) {
      debug.ws.error('Failed to create WebSocket', { error: error.message });
      console.error('LiveRefresh: Failed to create WebSocket:', error);
      setConnectionError('Failed to connect');
    }
  }, [maxReconnectAttempts, reconnectInterval, send, notifyListeners]);

  // Disconnect from WebSocket
  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close(1000, 'User disconnected');
      wsRef.current = null;
    }

    setIsConnected(false);
  }, []);

  // Auto-connect on mount
  useEffect(() => {
    if (autoConnect) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [autoConnect, connect, disconnect]);

  return {
    isConnected,
    lastMessage,
    connectionError,
    connect,
    disconnect,
    send,
    addEventListener,
    removeEventListener,
  };
}

/**
 * Hook for subscribing to specific event types
 * @param {string|string[]} eventTypes - Event type(s) to subscribe to
 * @param {Function} callback - Callback function when event is received
 * @param {Object} liveRefresh - LiveRefresh instance from useLiveRefresh
 */
export function useLiveRefreshEvent(eventTypes, callback, liveRefresh) {
  useEffect(() => {
    if (!liveRefresh?.addEventListener) return;

    const types = Array.isArray(eventTypes) ? eventTypes : [eventTypes];
    const cleanups = types.map(type =>
      liveRefresh.addEventListener(type, callback)
    );

    return () => {
      cleanups.forEach(cleanup => cleanup());
    };
  }, [eventTypes, callback, liveRefresh]);
}

/**
 * Context provider for sharing LiveRefresh across components
 */
import { createContext, useContext } from 'react';

export const LiveRefreshContext = createContext(null);

export function LiveRefreshProvider({ children }) {
  const liveRefresh = useLiveRefresh();

  return (
    <LiveRefreshContext.Provider value={liveRefresh}>
      {children}
    </LiveRefreshContext.Provider>
  );
}

export function useLiveRefreshContext() {
  const context = useContext(LiveRefreshContext);
  if (!context) {
    throw new Error('useLiveRefreshContext must be used within a LiveRefreshProvider');
  }
  return context;
}

export default useLiveRefresh;
