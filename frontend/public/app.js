// --- DARK MODE THEME TOGGLE (SA SISTEMSKOM DETEKCIJOM) ---
const themeToggle = document.getElementById('themeToggle');
const themeIcon = document.getElementById('themeIcon');
const themeText = document.getElementById('themeText');

// 1. Check if user previously explicitly saved a preference
let currentTheme = localStorage.getItem('theme');

// 2. If no saved preference, check their OS/Browser settings!
if (!currentTheme) {
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
        currentTheme = 'dark';
    } else {
        currentTheme = 'light';
    }
}

// 3. Apply the theme on initial load
if (currentTheme === 'dark') {
    document.body.classList.add('dark-mode');
    themeIcon.innerText = '☀️';
    themeText.innerText = 'Svijetla';
}

// 4. Toggle on click and save their manual override
themeToggle.addEventListener('click', () => {
    document.body.classList.toggle('dark-mode');
    let theme = 'light';
    if (document.body.classList.contains('dark-mode')) {
        theme = 'dark';
        themeIcon.innerText = '☀️';
        themeText.innerText = 'Svijetla';
    } else {
        themeIcon.innerText = '🌙';
        themeText.innerText = 'Tamna';
    }
    localStorage.setItem('theme', theme);
});
// ---------------------------------------------------------

const PUBLIC_VAPID_KEY = 'BEDB1bl2ezxa6lOPhctgVecX6hNRZNQt6AY_n5Q7Cshi7hVcJkUFpBUWxS04m1pw1E9R4SO_Y0aiszjYBMCc2co';
const API_BASE_URL = '/api/v1';

const map = L.map('map').setView([44.2056, 17.9077], 7);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);

let userMarker = null;

const cityInput = document.getElementById('cityInput');
const streetInput = document.getElementById('streetInput');
const numberInput = document.getElementById('numberInput');
const subBtn = document.getElementById('subBtn');
const statusDiv = document.getElementById('status');

function validateInputs() {
    if (cityInput.value.trim().length > 1 && streetInput.value.trim().length > 1) {
        subBtn.disabled = false;
    } else {
        subBtn.disabled = true;
    }
}

cityInput.addEventListener('input', validateInputs);
streetInput.addEventListener('input', validateInputs);

// --- BULLETPROOF SRE STATS LOADER ---
async function loadStats() {
    try {
        const res = await fetch(`${API_BASE_URL}/stats/overview`);
        if (!res.ok) throw new Error("API Connection Failed");
        
        const stats = await res.json();
        
        // 1. Update the Green Banner
        document.getElementById('statOutages').innerText = stats.active_outages ?? '--';
        document.getElementById('statUsers').innerText = stats.protected_users ?? '--';
        
        // 2. Update the Dark SRE Badges
        document.getElementById('badge-outages').innerText = stats.active_outages ?? '--';
        document.getElementById('badge-provider').innerText = stats.top_distributor ?? '--';
        document.getElementById('badge-latency').innerText = stats.scraper_latency_avg ?? '--';
        document.getElementById('badge-sync').innerText = stats.last_sync ?? '--';
    } catch (err) {
        console.error("Failed to load stats:", err);
        document.getElementById('statOutages').innerText = '--';
        document.getElementById('statUsers').innerText = '--';
    }
}

async function loadOutages() {
    try {
        const res = await fetch(`${API_BASE_URL}/outages/active`);
        const outages = await res.json();
        outages.forEach(outage => {
            if (outage.lat && outage.lng) {
                L.marker([outage.lat, outage.lng])
                 .bindPopup(`<b>${outage.municipality}</b><br>${outage.area}`)
                 .addTo(map);
            }
        });
    } catch (err) {
        console.error("Failed to load outages:", err);
    }
}

map.on('click', async function(e) {
    const lat = e.latlng.lat;
    const lng = e.latlng.lng;

    if (userMarker) map.removeLayer(userMarker);
    userMarker = L.marker([lat, lng], {
        icon: L.icon({
            iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png',
            shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
            iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34], shadowSize: [41, 41]
        })
    }).addTo(map);

    statusDiv.innerHTML = "<i>Tražim lokaciju na karti... ⏳</i>";

    try {
        const res = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}&zoom=18&addressdetails=1`);
        const data = await res.json();
        const address = data.address || {};
        
        const street = address.road || address.pedestrian || address.suburb || "BB";
        const municipality = address.city || address.town || address.village || address.municipality || "";
        const house_number = address.house_number || "";

        cityInput.value = municipality;
        streetInput.value = street === "BB" ? "" : street;
        numberInput.value = house_number;
        
        statusDiv.innerHTML = "";
        validateInputs();

    } catch (err) {
        statusDiv.innerHTML = `<span style="color:red;">Greška pri lociranju sa karte. Molimo unesite ručno.</span>`;
    }
});

async function subscribePush() {
    const municipality = cityInput.value.trim();
    const street = streetInput.value.trim();
    const house_number = numberInput.value.trim();

    try {
        statusDiv.innerHTML = "⏳ Povezivanje...";
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
                street_name: street,
                municipality: municipality,
                house_number: house_number,
                push_endpoint: subData.endpoint,
                push_keys: subData.keys,
                is_rural: false
            })
        });
          
        if (res.ok) {
            statusDiv.innerHTML = "✅ Uspješno ste prijavljeni za obavijesti!";
            loadStats();
        } else {
            throw new Error("Greška na serveru");
        }
    } catch (err) {
        statusDiv.innerHTML = `❌ Greška: ${err.message}`;
    }
}

loadStats();
loadOutages();
