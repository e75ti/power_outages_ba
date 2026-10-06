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
