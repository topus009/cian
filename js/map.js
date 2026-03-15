/** Карта Leaflet и маркеры */
let map;
const markers = [];
const metroMarkers = [];

const TILE_LAYERS = {
    'OSM Standard':        { url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',           attr: '&copy; OpenStreetMap' },
    'OSM Hot':             { url: 'https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png',         attr: '&copy; OpenStreetMap, HOT' },
    'Транспорт (ÖPNV)':   { url: 'https://tileserver.memomaps.de/tilegen/{z}/{x}/{y}.png',        attr: '&copy; OpenStreetMap &copy; MeMoMaps' },
    'CyclOSM':             { url: 'https://{s}.tile-cyclosm.openstreetmap.fr/cyclosm/{z}/{x}/{y}.png', attr: '&copy; OpenStreetMap &copy; CyclOSM' },
    'CartoDB Positron':    { url: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', attr: '&copy; OpenStreetMap &copy; CARTO' },
    'CartoDB Voyager':     { url: 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', attr: '&copy; OpenStreetMap &copy; CARTO' },
    'OpenTopoMap':         { url: 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',              attr: '&copy; OpenStreetMap &copy; OpenTopoMap' },
    'Dark (CartoDB)':      { url: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',  attr: '&copy; OpenStreetMap &copy; CARTO' },
    'Dark ч/б (Positron)': { url: 'https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png', attr: '&copy; OpenStreetMap &copy; CARTO' },
};

function getSavedLayer() {
    try { return localStorage.getItem('map_tile_layer') || ''; } catch(e) { return ''; }
}
function saveLayer(name) {
    try { localStorage.setItem('map_tile_layer', name); } catch(e) {}
}

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

    const savedName = getSavedLayer();
    const defaultName = TILE_LAYERS[savedName] ? savedName : 'OSM Standard';
    let currentTile = L.tileLayer(TILE_LAYERS[defaultName].url, {
        attribution: TILE_LAYERS[defaultName].attr, maxZoom: 19
    }).addTo(map);

    // Контрол-селект выбора слоя
    const LayerSelect = L.Control.extend({
        options: { position: 'topright' },
        onAdd: function () {
            const wrap = L.DomUtil.create('div', 'leaflet-bar layer-select-wrap');
            const sel = L.DomUtil.create('select', 'layer-select', wrap);
            Object.keys(TILE_LAYERS).forEach(function (name) {
                const opt = document.createElement('option');
                opt.value = name; opt.textContent = name;
                if (name === defaultName) opt.selected = true;
                sel.appendChild(opt);
            });
            L.DomEvent.disableClickPropagation(wrap);
            L.DomEvent.disableScrollPropagation(wrap);
            sel.addEventListener('change', function () {
                const picked = sel.value;
                map.removeLayer(currentTile);
                currentTile = L.tileLayer(TILE_LAYERS[picked].url, {
                    attribution: TILE_LAYERS[picked].attr, maxZoom: 19
                }).addTo(map);
                saveLayer(picked);
            });
            return wrap;
        }
    });
    new LayerSelect().addTo(map);

    // Режим отображения квартир: только видимые / видимые + последние скрытые / все
    const VisibilitySelect = L.Control.extend({
        options: { position: 'topright' },
        onAdd: function () {
            const wrap = L.DomUtil.create('div', 'leaflet-bar layer-select-wrap visibility-select-wrap');
            const sel = L.DomUtil.create('select', 'layer-select visibility-select', wrap);
            const options = [
                { value: 'visible', text: 'Только видимые' },
                { value: 'visible_plus_newly', text: 'Видимые + последние скрытые' },
                { value: 'all', text: 'Все' }
            ];
            const currentMode = (typeof window.CIAN_VISIBILITY_MODE !== 'undefined' ? window.CIAN_VISIBILITY_MODE : null) || (function () { try { return localStorage.getItem('cian_visibility_mode') || 'visible'; } catch (e) { return 'visible'; } })();
            options.forEach(function (o) {
                const opt = document.createElement('option');
                opt.value = o.value;
                opt.textContent = o.text;
                if (o.value === currentMode) opt.selected = true;
                sel.appendChild(opt);
            });
            L.DomEvent.disableClickPropagation(wrap);
            L.DomEvent.disableScrollPropagation(wrap);
            sel.addEventListener('change', function () {
                const value = sel.value;
                try { localStorage.setItem('cian_visibility_mode', value); } catch (e) {}
                window.location.reload();
            });
            return wrap;
        }
    });
    new VisibilitySelect().addTo(map);

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

    // Станции метро — отдельный слой, метки по цвету линии
    const metroStations = window.METRO_SPB || [];
    metroStations.forEach((st) => {
        const color = st.line_color || '#888';
        const icon = L.divIcon({
            className: 'metro-marker',
            html: '<div class="metro-marker-dot" style="background:' + color + ';border-color:' + color + '"></div>',
            iconSize: [10, 10],
            iconAnchor: [5, 5]
        });
        const m = L.marker([st.lat, st.lon], { icon }).addTo(map);
        m._isMetro = true;
        m.bindPopup('<strong>Метро</strong> ' + (st.name || '') + '<br><small>' + st.lat + ', ' + st.lon + '</small>');
        metroMarkers.push(m);
    });

    const valid = apartments.filter(a => a.lat != null && a.lon != null);
    if (valid.length) {
        const b = L.latLngBounds(valid.map(a => [a.lat, a.lon]));
        map.fitBounds(b, { padding: [30, 30] });
    }
}
