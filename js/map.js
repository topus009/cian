/** Карта Leaflet и маркеры */
let map;
const markers = [];

function createIcon(rating) {
    const isClosed = rating === 4;
    const c = getRatingColor(rating);
    const style = isClosed
        ? 'background:rgba(156,163,175,0.45);width:22px;height:22px;border-radius:50%;border:2px solid rgba(255,255,255,0.6);box-shadow:0 1px 3px rgba(0,0,0,0.2);'
        : 'background:' + c + ';width:22px;height:22px;border-radius:50%;border:2px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,0.3);';
    return L.divIcon({
        className: 'custom-marker' + (isClosed ? ' marker-closed' : ''),
        html: '<div style="' + style + '"></div>',
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
        if (apt.lat == null || apt.lon == null) return;
        const rating = getRating(apt.url);
        const marker = L.marker([apt.lat, apt.lon], { icon: createIcon(rating) }).addTo(map);
        marker._apt = apt;
        const aptId = (apt.url || '').match(/\/(\d+)\/?$/);
        const code = aptId ? aptId[1] : '';
        const area = apt.total_area ? apt.total_area + ' м²' : '';
        const price = (apt.price || '').replace(/</g, '&lt;');
        const parts = [code ? 'Код ' + code : '', area, price].filter(Boolean);
        marker.bindPopup(parts.join(' · '));
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
