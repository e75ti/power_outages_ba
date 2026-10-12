const CACHE_NAME = 'power-alerts-v1';
const ASSETS = [
    '/',
    '/index.html',
    '/app.js',
    '/manifest.json',
    '/icon-192x192.png',
    '/icon-512x512.png'
];

self.addEventListener('install', function(event) {
    self.skipWaiting();
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => cache.addAll(ASSETS))
    );
});

self.addEventListener('activate', function(event) {
    event.waitUntil(clients.claim());
});

self.addEventListener('fetch', function(event) {
    // Preskačemo API pozive, keširamo samo frontend
    if (event.request.method === 'GET' && !event.request.url.includes('/api/')) {
        event.respondWith(
            caches.match(event.request).then(response => {
                return response || fetch(event.request);
            })
        );
    }
});

self.addEventListener('push', function(event) {
    const data = event.data ? event.data.json() : {};
    event.waitUntil(
        self.registration.showNotification(data.title || 'Nestanak struje', {
            body: data.body || 'Najavljen je nestanak struje na vašoj adresi.',
            icon: data.icon || 'https://cdn-icons-png.flaticon.com/512/616/616430.png',
            tag: data.tag || 'outage'
        })
    );
});

self.addEventListener('notificationclick', function(event) {
    event.notification.close();
    event.waitUntil(clients.openWindow('/'));
});
