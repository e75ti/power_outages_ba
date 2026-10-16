console.log("App Version 2.0 Loaded - Cache Successfully Cleared");

// --- iOS DETECTION & PWA PROMPT ---
function checkIOSAndPrompt() {
    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
    const isStandalone = window.navigator.standalone === true || window.matchMedia('(display-mode: standalone)').matches;

    if (isIOS && !isStandalone) {
        const iosPrompt = document.createElement('div');
        iosPrompt.style.cssText = `
            position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%);
            background: rgba(30, 41, 59, 0.95); color: white; padding: 15px 20px;
            border-radius: 12px; box-shadow: 0 10px 25px rgba(0,0,0,0.3);
            text-align: center; z-index: 9999; width: 90%; max-width: 400px;
            border: 1px solid #3b82f6; font-size: 14px;
        `;
        iosPrompt.innerHTML = `
            <strong>🍎 Koristite iPhone?</strong><br>
            Apple ne dozvoljava obavijesti u Safariju. <br><br>
            Kliknite ikonicu za dijeljenje (<strong>Share</strong>) na dnu ekrana i odaberite 
            <br><strong>"Add to Home Screen"</strong>.<br>
            Zatim otvorite aplikaciju sa početnog zaslona!
            <button onclick="this.parentElement.remove()" style="
                margin-top: 10px; width: 100%; padding: 8px; border: none; 
                border-radius: 6px; background: #3b82f6; color: white; font-weight: bold; cursor: pointer;
            ">U redu, razumijem</button>
        `;
        document.body.appendChild(iosPrompt);
        
        const subBtn = document.getElementById('subBtn');
        subBtn.disabled = true;
        subBtn.innerText = "Zaključano (Dodajte na početni zaslon)";
    }
}
document.addEventListener('DOMContentLoaded', checkIOSAndPrompt);

// --- THEME TOGGLE ---
const themeToggle = document.getElementById('themeToggle');
const themeIcon = document.getElementById('themeIcon');
const themeText = document.getElementById('themeText');
let currentTheme = localStorage.getItem('theme') || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');

if (currentTheme === 'dark') {
    document.body.classList.add('dark-mode');
    themeIcon.innerText = '☀️';
    themeText.innerText = 'Svijetla';
}

themeToggle.addEventListener('click', () => {
    document.body.classList.toggle('dark-mode');
    const isDark = document.body.classList.contains('dark-mode');
    themeIcon.innerText = isDark ? '☀️' : '🌙';
    themeText.innerText = isDark ? 'Svijetla' : 'Tamna';
    localStorage.setItem('theme', isDark ? 'dark' : 'light');
});

// --- CORE LOGIC & MOBILE FIX ---
const PUBLIC_VAPID_KEY = 'BEDB1bl2ezxa6lOPhctgVecX6hNRZNQt6AY_n5Q7Cshi7hVcJkUFpBUWxS04m1pw1E9R4SO_Y0aiszjYBMCc2co';

function urlB64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding).replace(/\-/g, '+').replace(/_/g, '/');
    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);
    for (let i = 0; i < rawData.length; ++i) { outputArray[i] = rawData.charCodeAt(i); }
    return outputArray;
}

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
    const isIOSBlocked = subBtn.innerText.includes("Zaključano");
    subBtn.disabled = isIOSBlocked || cityInput.value.trim().length < 2 || streetInput.value.trim().length < 2;
}

cityInput.addEventListener('input', validateInputs);
streetInput.addEventListener('input', validateInputs);

async function loadStats() {
    try {
        const res = await fetch(`${API_BASE_URL}/stats/overview`);
        if (!res.ok) throw new Error("API Connection Failed");
        const stats = await res.json();
        
        document.getElementById('statOutages').innerText = stats.active_outages ?? '--';
        document.getElementById('statUsers').innerText = stats.protected_users ?? '--';
        document.getElementById('badge-outages').innerText = stats.active_outages ?? '--';
        document.getElementById('badge-provider').innerText = stats.top_distributor ?? '--';
        document.getElementById('badge-latency').innerText = stats.scraper_latency_avg ?? '--';
        document.getElementById('badge-sync').innerText = stats.last_sync ?? '--';
    } catch (err) {
        console.error("Failed to load stats:", err);
    }
}

async function loadOutages() {
    try {
        const res = await fetch(`${API_BASE_URL}/outages/active`);
        const outages = await res.json();
        
        // PERFORMANCE FIX: Leaflet MarkerCluster
        const markers = L.markerClusterGroup({
            chunkedLoading: true,
            maxClusterRadius: 50
        });
        
        outages.forEach(outage => {
            if (outage.lat && outage.lng) {
                const marker = L.marker([outage.lat, outage.lng])
                 .bindPopup(`<b>${outage.municipality}</b><br>${outage.area}`);
                markers.addLayer(marker);
            }
        });
        
        map.addLayer(markers);
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
    statusDiv.style.color = "var(--text-main)";

    try {
        const res = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}&zoom=18&addressdetails=1`);
        const data = await res.json();
        const address = data.address || {};
        
        const street = address.road || address.pedestrian || address.suburb || "BB";
        cityInput.value = address.city || address.town || address.village || address.municipality || "";
        streetInput.value = street === "BB" ? "" : street;
        numberInput.value = address.house_number || "";
        
        statusDiv.innerHTML = "";
        validateInputs();
        
        // Auto-scroll up to the Subscribe button so the user knows what to do next
        document.getElementById('subBtn').scrollIntoView({ behavior: 'smooth', block: 'center' });
    } catch (err) {
        statusDiv.innerHTML = "❌ Greška pri lociranju. Molimo unesite ručno.";
        statusDiv.style.color = "red";
    }
});

async function subscribePush() {
    const municipality = cityInput.value.trim();
    const street = streetInput.value.trim();
    const house_number = numberInput.value.trim();

    try {
        statusDiv.innerHTML = "⏳ Generišem sigurni ključ...<br><span style='font-size: 0.85em; color: var(--text-subtitle);'>Ovo može potrajati nekoliko sekundi zavisno od vaše mreže. Ne zatvarajte prozor.</span>";
        statusDiv.style.color = "var(--text-main)";
        
        const permission = await Notification.requestPermission();
        if (permission !== 'granted') throw new Error('Notifikacije su blokirane u vašem pregledniku. Morate ih dozvoliti u postavkama (kliknite katanac pored URL adrese.');

        // 1. Pokreni registraciju
        await navigator.serviceWorker.register('/sw.js');
        
        // Wait Service Worker bude 100% spreman
        const registration = await navigator.serviceWorker.ready;
        
        // Da li već postoji pretplata za ovaj uređaj?
        let subscription = await registration.pushManager.getSubscription();
        
        if (subscription) {
            console.log("Korisnik već ima aktivan Push ključ. Koristim postojeći za novu ulicu.");
            // NE radimo unsubscribe!
        } else {
            console.log("Pravim novi Push ključ...");
            // Ako nema pretplate, tek onda pravimo novu sa onim bitnim Uint8Array konverterom
            subscription = await registration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: urlB64ToUint8Array(PUBLIC_VAPID_KEY)
            });
        }

        const subData = subscription.toJSON();
        
        const isRuralChecked = document.getElementById('ruralInput') ? document.getElementById('ruralInput').checked : false;

        const res = await fetch(`${API_BASE_URL}/subscribe`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                street_name: street,
                municipality: municipality,
                house_number: house_number,
                push_endpoint: subData.endpoint,
                push_keys: subData.keys,
                is_rural: isRuralChecked
            })
        });
          
        if (res.ok) {
            statusDiv.innerHTML = "✅ Uspješno ste prijavljeni za obavijesti!";
            statusDiv.style.color = "#10b981";
            loadStats(); // Osvježi statistiku
        } else {
            throw new Error("Greška na serveru");
        }
    } catch (err) {
        statusDiv.innerHTML = `❌ Greška: ${err.message}`;
        statusDiv.style.color = "red";
    }
}

loadStats();
loadOutages();
