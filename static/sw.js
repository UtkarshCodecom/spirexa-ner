/* Service worker for offline field use.
 *
 * Two jobs:
 *   1. Keep the dashboard and the latest risk snapshot readable with no signal.
 *   2. Never lose a field report submitted while offline.
 *
 * Strategy is network-first with a cache fallback, so a device with signal
 * always sees fresh risk data, and one without falls back to the last sync
 * rather than a browser error page.
 */

const CACHE = 'slopewatch-v1';
const SHELL = ['/', '/static/manifest.json'];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const { request } = event;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  // /api/predict needs a live satellite query; there is no useful cached
  // answer for an arbitrary coordinate, so let it fail honestly when offline.
  if (url.pathname === '/api/predict') return;

  event.respondWith(
    fetch(request)
      .then(response => {
        if (response && response.status === 200) {
          const copy = response.clone();
          caches.open(CACHE).then(c => c.put(request, copy));
        }
        return response;
      })
      .catch(() => caches.match(request).then(hit => hit || caches.match('/')))
  );
});

// Fired by the page when it queues a report, and by the browser when
// connectivity returns.
self.addEventListener('sync', event => {
  if (event.tag === 'flush-reports') {
    event.waitUntil(notifyClientsToFlush());
  }
});

async function notifyClientsToFlush() {
  const clients = await self.clients.matchAll({ includeUncontrolled: true });
  clients.forEach(c => c.postMessage({ type: 'flush-reports' }));
}

self.addEventListener('message', event => {
  if (event.data && event.data.type === 'skip-waiting') self.skipWaiting();
});
