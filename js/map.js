/** Карта Leaflet и маркеры */
let map;
const markers = [];

function createIcon(rating) {
    const c = getRatingColor(rating);
    return L.divIcon({
        className: 'custom-marker',
        html: '<div style="background:' + c + ';width:22px;height:22px;border-radius:50%;border:2px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,0.3);"></div>',
        iconSize: [22, 22], iconAnchor: [11, 11]
    });
}

function updateMarkerIcon(apt, rating) {
    const m = markers.find(mr => mr._apt && mr._apt.url === apt.url);
    if (m) m.setIcon(createIcon(rating));
}

function initMap(apartments) {
    map = L.map('map').setView([59.9343, 30.3351], 11);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
    }).addTo(map);

    apartments.forEach((apt) => {
        const rating = getRating(apt.url);
        const marker = L.marker([apt.lat, apt.lon], { icon: createIcon(rating) }).addTo(map);
        marker._apt = apt;
        marker.bindPopup('<b>' + (apt.title || '').replace(/</g, '&lt;') + '</b><br>' + (apt.address || '') + '<br><a href="' + apt.url + '" target="_blank">Открыть на Циан</a>');
        marker.on('click', function () {
            document.querySelectorAll('.apartment').forEach(el => el.classList.remove('highlighted'));
            const el = document.querySelector('.apartment[data-url="' + apt.url.replace(/"/g, '\\"') + '"]');
            if (el) { el.classList.add('highlighted'); el.scrollIntoView({ behavior: 'smooth', block: 'center' }); }
        });
        markers.push(marker);
    });

    const valid = apartments.filter(a => a.lat != null && a.lon != null);
    if (valid.length) {
        const b = L.latLngBounds(valid.map(a => [a.lat, a.lon]));
        map.fitBounds(b, { padding: [30, 30] });
    }
}
