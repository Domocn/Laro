// Bump CACHE_NAME whenever the app shell changes so clients drop stale HTML/JS.
const CACHE_NAME = 'laro-v8';
// Bump API_CACHE_NAME when API caching strategy changes (forces clients to drop stale lists).
const API_CACHE_NAME = 'laro-api-v5';
const STATIC_ASSETS = [
  '/manifest.json',
];

// API endpoints that can be cached for offline use (match real FastAPI mounts).
// Do NOT cache /recipes or /meal-plans — stale SW entries made deleted recipes
// reappear under All after a successful DELETE.
const CACHEABLE_API_PATTERNS = [
  '/api/shopping-lists',
  '/api/pantry',
  '/api/households',
  '/api/categories',
  // legacy mistaken paths (keep harmless)
  '/api/v1/shopping-lists',
  '/api/v1/pantry',
  '/api/v1/households',
  '/api/v1/categories',
];

// Cache duration in milliseconds (5 minutes for API data)
const API_CACHE_MAX_AGE = 5 * 60 * 1000;

// Install event - cache static assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('Laro: Caching static assets');
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
  const currentCaches = [CACHE_NAME, API_CACHE_NAME];
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => !currentCaches.includes(name))
          .map((name) => caches.delete(name))
      );
    })
  );
  self.clients.claim();
});

// Message handler for cache control from the app
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'CLEAR_API_CACHE') {
    event.waitUntil(
      caches.delete(API_CACHE_NAME).then(() => {
        console.log('Mise SW: API cache cleared');
        event.ports[0]?.postMessage({ success: true });
      })
    );
  }

  if (event.data && event.data.type === 'INVALIDATE_PATTERN') {
    const pattern = event.data.pattern;
    event.waitUntil(
      caches.open(API_CACHE_NAME).then(async (cache) => {
        const keys = await cache.keys();
        const toDelete = keys.filter(req => req.url.includes(pattern));
        await Promise.all(toDelete.map(req => cache.delete(req)));
        console.log('Mise SW: Invalidated', toDelete.length, 'cached entries for', pattern);
        event.ports[0]?.postMessage({ success: true, count: toDelete.length });
      })
    );
  }
});

// Check if URL matches cacheable API patterns
function isCacheableApi(url) {
  return CACHEABLE_API_PATTERNS.some(pattern => url.includes(pattern));
}

// Fetch event - network first, fallback to cache
self.addEventListener('fetch', (event) => {
  // Skip non-GET requests
  if (event.request.method !== 'GET') return;

  const url = event.request.url;

  // Handle cacheable API requests with stale-while-revalidate
  if (url.includes('/api/') && isCacheableApi(url)) {
    event.respondWith(handleApiRequest(event.request));
    return;
  }

  // Skip non-cacheable API requests - always go to network
  if (url.includes('/api/')) {
    return;
  }

  // Navigations / HTML must always hit the network so deploys are not stuck
  // behind a cached index.html that points at old hashed bundles.
  const accept = event.request.headers.get('accept') || '';
  const isHtmlNav =
    event.request.mode === 'navigate' ||
    accept.includes('text/html') ||
    url.endsWith('/') ||
    url.endsWith('/index.html');

  if (isHtmlNav) {
    event.respondWith(
      fetch(event.request).catch(() =>
        caches.match(event.request).then((cached) => cached || new Response('Offline', { status: 503 }))
      )
    );
    return;
  }

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        // Clone the response before caching
        const responseClone = response.clone();

        // Cache hashed static assets only (not HTML)
        if (response.status === 200 && url.includes('/static/')) {
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseClone);
          });
        }

        return response;
      })
      .catch(() => {
        // Fallback to cache if network fails
        return caches.match(event.request).then((cachedResponse) => {
          if (cachedResponse) {
            return cachedResponse;
          }
          return new Response('Offline', { status: 503 });
        });
      })
  );
});

// Network-first for API lists. Stale-while-revalidate hid freshly imported
// recipes / meal plans behind a cached empty [] for up to API_CACHE_MAX_AGE.
async function handleApiRequest(request) {
  const cache = await caches.open(API_CACHE_NAME);

  try {
    const response = await fetch(request);
    if (response.ok) {
      const responseToCache = response.clone();
      const headers = new Headers(responseToCache.headers);
      headers.set('x-sw-cached-at', Date.now().toString());
      const cachedBody = await responseToCache.blob();
      await cache.put(
        request,
        new Response(cachedBody, {
          status: responseToCache.status,
          statusText: responseToCache.statusText,
          headers,
        })
      );
    }
    return response;
  } catch (error) {
    console.log('Laro SW: Network request failed, using cache', error);
    const cachedResponse = await cache.match(request);
    if (cachedResponse) {
      const cachedAt = parseInt(cachedResponse.headers.get('x-sw-cached-at') || '0', 10);
      const age = Date.now() - cachedAt;
      // Only serve offline cache if it is reasonably fresh
      if (!cachedAt || age < API_CACHE_MAX_AGE * 12) {
        return cachedResponse;
      }
    }
    return new Response(JSON.stringify({ error: 'Offline and no cached data' }), {
      status: 503,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}

// Handle push notifications
self.addEventListener('push', (event) => {
  console.log('Laro: Push notification received');

  let payload = {
    title: 'Laro',
    body: 'You have a new notification',
    icon: '/icons/icon-192x192.png',
    badge: '/icons/icon-72x72.png',
    url: '/',
  };

  if (event.data) {
    try {
      payload = { ...payload, ...event.data.json() };
    } catch (e) {
      payload.body = event.data.text() || payload.body;
    }
  }

  const options = {
    body: payload.body,
    icon: payload.icon || '/icons/icon-192x192.png',
    badge: payload.badge || '/icons/icon-72x72.png',
    vibrate: [100, 50, 100],
    tag: payload.tag || 'laro-notification',
    renotify: true,
    requireInteraction: payload.requireInteraction || false,
    data: {
      url: payload.url || '/',
      timestamp: Date.now(),
      ...(payload.data || {}),
    },
    actions: payload.actions || [],
  };

  event.waitUntil(
    self.registration.showNotification(payload.title || 'Laro', options)
  );
});

// Handle notification clicks
self.addEventListener('notificationclick', (event) => {
  console.log('Laro: Notification clicked');
  event.notification.close();

  const urlToOpen = event.notification.data?.url || '/';

  // Handle action buttons
  if (event.action) {
    switch (event.action) {
      case 'view-meal':
        event.waitUntil(clients.openWindow('/meal-planner'));
        return;
      case 'view-recipe':
        event.waitUntil(clients.openWindow(urlToOpen));
        return;
      case 'dismiss':
        return;
    }
  }

  // Default: open the app
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windowClients) => {
      // Check if there's already a window open
      for (const client of windowClients) {
        if (client.url.includes(self.location.origin) && 'focus' in client) {
          client.navigate(urlToOpen);
          return client.focus();
        }
      }
      // If no window is open, open a new one
      return clients.openWindow(urlToOpen);
    })
  );
});

// Handle notification close
self.addEventListener('notificationclose', (event) => {
  console.log('Laro: Notification closed', event.notification.tag);
});

// Background sync for offline actions (future feature)
self.addEventListener('sync', (event) => {
  console.log('Laro: Background sync', event.tag);
  
  if (event.tag === 'sync-recipes') {
    event.waitUntil(syncRecipes());
  }
});

async function syncRecipes() {
  // Future: sync offline recipe changes
  console.log('Laro: Syncing recipes...');
}

// Periodic background sync for meal reminders
self.addEventListener('periodicsync', (event) => {
  if (event.tag === 'meal-reminder-check') {
    event.waitUntil(checkMealReminders());
  }
});

async function checkMealReminders() {
  // This would be called periodically to check for upcoming meals
  console.log('Laro: Checking meal reminders...');
}
