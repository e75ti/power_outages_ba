const PUBLIC_VAPID_KEY = 'BEDB1bl2ezxa6lOPhctgVecX6hNRZNQt6AY_n5Q7Cshi7hVcJkUFpBUWxS04m1pw1E9R4SO_Y0aiszjYBMCc2co';
const API_BASE_URL = '/api/v1';

const map = L.map('map').setView([44.2056, 17.9077], 7);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);

let userMarker = null;

// HTML Elements
const cityInput = document.getElementById('cityInput');
const streetInput = document.getElementById('streetInput');
const numberInput = document.getElementById('numberInput');
const subBtn = document.getElementById('subBtn');
const statusDiv = document.getElementById('status');

// Enable button only if required fields have text
function validateInputs() {
    if (cityInput.value.trim().length > 1 && streetInput.value.trim().length > 1) {
        subBtn.disabled = false;
    } else {
        subBtn.disabled = true;
    }
}

cityInput.addEventListener('input', validateInputs);
streetInput.addEventListener('input', validateInputs);

async function loadStats() {
    try {
        const res = await fetch(`${API_BASE_URL}/stats`);
        const stats = await res.json();
        document.getElementById('statOutages').innerText = stats.active_outages;
        document.getElementById('statUsers').innerText = stats.protected_users;
    } catch (err) {
        console.error("Failed to load stats:", err);
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

// Map Click -> Reverse Geocode -> Auto-fill inputs
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

        // Auto-fill the inputs so the user can review/edit them!
        cityInput.value = municipality;
        streetInput.value = street === "BB" ? "" : street;
        numberInput.value = house_number;
        
        statusDiv.innerHTML = "";
        validateInputs(); // Trigger validation to unlock button

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
                is_rural: false // Backend handles low-confidence radius anyway
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
