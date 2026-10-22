const CACHE = 'asistente-unilibre-v5';
const ASSETS = [
  '/',
  '/index.html',
  '/screens/programas/index.html',
  '/screens/citas/index.html',
  '/screens/proceso/index.html',
  '/screens/asesor/index.html',
  '/manifest.json',
  '/icons/icon-192.png',
  '/icons/icon-512.png',
  '/icons/unilibre-escudo.png',
  '/icons/unilibre-mark.png',
  '/styles/unilibre.css',
  '/js/programas-unilibre.js'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE)
      .then((cache) => cache.addAll(ASSETS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

// Network-first: online users always get the latest deploy; offline users
// fall back to the last successfully cached copy (and to the chat shell
// for unknown routes, so the app still opens instead of showing an error).
self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        const copy = response.clone();
        caches.open(CACHE).then((cache) => cache.put(event.request, copy));
        return response;
      })
      .catch(() => caches.match(event.request).then((cached) => cached || caches.match('/index.html')))
  );
});
