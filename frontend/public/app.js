const PUBLIC_VAPID_KEY = 'BEDB1bl2ezxa6lOPhctgVecX6hNRZNQt6AY_n5Q7Cshi7hVcJkUFpBUWxS04m1pw1E9R4SO_Y0aiszjYBMCc2co'; // <-- PASTE YOUR KEY HERE
const API_BASE_URL = '/api/v1';

const map = L.map('map').setView([44.2056, 17.9077], 7);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);

async function loadOutages() {
    const res = await fetch(`${API_BASE_URL}/outages/active`);
    const outages = await res.json();
    outages.forEach(outage => {
        if (outage.lat && outage.lng) {
            L.marker([outage.lat, outage.lng])
             .bindPopup(`<b>${outage.municipality}</b><br>${outage.area}`)
             .addTo(map);
        }
    });
}

async function subscribePush() {
    const status = document.getElementById('status');
    const street = document.getElementById('street').value.trim();
    const city = document.getElementById('city').value.trim();

    try {
        status.innerHTML = "⏳ Povezivanje...";
        const permission = await Notification.requestPermission();
        if (permission !== 'granted') throw new Error('Notifikacije odbijene.');

        const registration = await navigator.serviceWorker.register('/sw.js');
        const subscription = await registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: PUBLIC_VAPID_KEY
        });

        const subData = subscription.toJSON();
        const res = await fetch(`${API_BASE_URL}/subscribe`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                street_name: street, municipality: city,
                push_endpoint: subData.endpoint, push_keys: subData.keys
            })
        });
        
        if (res.ok) status.innerHTML = "✅ Uspješno ste prijavljeni!";
    } catch (err) {
        status.innerHTML = `❌ Greška: ${err.message}`;
    }
}
loadOutages();
