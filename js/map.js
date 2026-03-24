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

/** Число комнат для подписи в маркере (как в list.js getRoomsCount). */
function getRoomsCountForMarker(apt) {
    if (typeof getRoomsCount === 'function') return getRoomsCount(apt);
    var t0 = apt && apt.title || '';
    var av = t0.match(/^(\d)-к\.\s*квартир/i);
    if (av) return Math.min(parseInt(av[1], 10), 5);
    var t = t0.toLowerCase();
    if (/1-комн|1-комнатн|однокомнатн/.test(t)) return 1;
    if (/2-комн|2-комнатн|двухкомнатн|двух комн/.test(t)) return 2;
    if (/3-комн|3-комнатн|трёхкомнатн|трехкомнатн/.test(t)) return 3;
    if (/5-комн|5-комнатн|пятикомнатн|пяти-комн|пяти\s*комн/.test(t)) return 5;
    if (/4-комн|4-комнатн|многокомнатн/.test(t)) return 4;
    return 0;
}

function roomsLabelForMarker(n) {
    if (n >= 5) return '5';
    if (n >= 4) return '4+';
    if (n >= 1) return String(n);
    return '?';
}

/**
 * @param {string} [outlineHex] — цвет обводки по выбранной сортировке (#rgb); иначе белая.
 */
function createIcon(rating, apt, outlineHex) {
    var isClosed = rating === 4;
    var c = getRatingColor(rating);
    var n = apt ? getRoomsCountForMarker(apt) : 0;
    var label = roomsLabelForMarker(n);
    var size = 26;
    var half = size / 2;
    var isAvito = apt && apt.source === 'avito';
    var radius = isAvito ? '5px' : '50%';
    var bg = isClosed ? 'rgba(156,163,175,0.45)' : c;
    var borderColor = outlineHex && outlineHex !== '#ffffff' ? outlineHex : null;
    var border = borderColor
        ? '3px solid ' + borderColor
        : (isClosed ? '2px solid rgba(255,255,255,0.6)' : '2px solid #fff');
    var color = isClosed ? '#374151' : '#fff';
    var shadow = isClosed ? '0 1px 3px rgba(0,0,0,0.2)' : '0 2px 6px rgba(0,0,0,0.3)';
    var inner =
        'display:flex;align-items:center;justify-content:center;' +
        'width:' + size + 'px;height:' + size + 'px;border-radius:' + radius + ';' +
        'background:' + bg + ';border:' + border + ';box-shadow:' + shadow + ';' +
        'color:' + color + ';font-size:11px;font-weight:700;line-height:1;' +
        'font-family:system-ui,-apple-system,sans-serif;' +
        (isClosed ? '' : 'text-shadow:0 1px 2px rgba(0,0,0,0.4);');
    return L.divIcon({
        className: 'custom-marker' + (isClosed ? ' marker-closed' : '') + (isAvito ? ' marker-avito' : ''),
        html: '<div class="marker-apt-inner" style="' + inner + '">' + label + '</div>',
        iconSize: [size, size],
        iconAnchor: [half, half]
    });
}

function getCompositeRangeForMap(field, stats) {
    if (field !== 'composite') return null;
    if (typeof window.getCompositeScoreRange === 'function') {
        return window.getCompositeScoreRange(window.APARTMENTS || [], stats);
    }
    return null;
}

function updateMarkerIcon(apt, rating) {
    var m = markers.find(function (mr) { return mr._apt && mr._apt.url === apt.url; });
    if (!m) return;
    var sel = document.getElementById('list-sort-select');
    var field = (sel && sel.value ? sel.value : 'rating-desc').split('-')[0];
    var stats = typeof getParamStats === 'function' ? getParamStats(window.APARTMENTS || []) : null;
    var compositeRange = getCompositeRangeForMap(field, stats);
    var outline =
        typeof window.getMarkerOutlineForSortField === 'function'
            ? window.getMarkerOutlineForSortField(apt, field, stats, compositeRange)
            : '#ffffff';
    m.setIcon(createIcon(rating, apt, outline));
}

/** Обновить обводку всех маркеров квартир под текущую сортировку в сайдбаре. */
function syncMapMarkerOutlines() {
    if (!map) return;
    var sel = document.getElementById('list-sort-select');
    var field = (sel && sel.value ? sel.value : 'rating-desc').split('-')[0];
    var stats = typeof getParamStats === 'function' ? getParamStats(window.APARTMENTS || []) : null;
    var compositeRange = getCompositeRangeForMap(field, stats);
    markers.forEach(function (m) {
        if (!m._apt || m._isMetro) return;
        var apt = m._apt;
        var r = getRating(apt.url);
        var outline =
            typeof window.getMarkerOutlineForSortField === 'function'
                ? window.getMarkerOutlineForSortField(apt, field, stats, compositeRange)
                : '#ffffff';
        m.setIcon(createIcon(r, apt, outline));
    });
}
window.syncMapMarkerOutlines = syncMapMarkerOutlines;

/**
 * Полная перерисовка маркеров квартир с актуальным getRating() (после переключения предустановок и т.п.).
 */
function refreshMapMarkersForCurrentFilter() {
    if (!map) return;
    var pool = window.APARTMENTS || [];
    var apartments =
        typeof filterApartmentsByRooms === 'function'
            ? filterApartmentsByRooms(pool)
            : pool;
    setMapApartmentMarkers(apartments);
}
window.refreshMapMarkersForCurrentFilter = refreshMapMarkersForCurrentFilter;

/** Перерисовать маркеры квартир (без метро). Вызывается при смене фильтра по комнатам. */
function setMapApartmentMarkers(apartments) {
    if (!map) return;
    markers.forEach(function (m) {
        map.removeLayer(m);
    });
    markers.length = 0;
    var sel = document.getElementById('list-sort-select');
    var field = (sel && sel.value ? sel.value : 'rating-desc').split('-')[0];
    var stats = typeof getParamStats === 'function' ? getParamStats(window.APARTMENTS || []) : null;
    var compositeRange = getCompositeRangeForMap(field, stats);
    (apartments || []).forEach(function (apt) {
        if (apt.lat == null || apt.lon == null) return;
        const rating = getRating(apt.url);
        var outline =
            typeof window.getMarkerOutlineForSortField === 'function'
                ? window.getMarkerOutlineForSortField(apt, field, stats, compositeRange)
                : '#ffffff';
        const marker = L.marker([apt.lat, apt.lon], { icon: createIcon(rating, apt, outline) }).addTo(map);
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

    const PresetRatingsToggle = L.Control.extend({
        options: { position: 'topright' },
        onAdd: function () {
            const wrap = L.DomUtil.create('div', 'leaflet-bar preset-ratings-wrap');
            const label = L.DomUtil.create('label', 'preset-ratings-label', wrap);
            const cb = L.DomUtil.create('input', '', label);
            cb.type = 'checkbox';
            cb.id = 'cian-preset-ratings-cb';
            cb.title = 'Показывать заранее выставленные оценки (6 приоритетных — отлично, остальные в списке — хорошо). Снимите, чтобы видеть только свои оценки из браузера.';
            cb.checked = typeof getPresetRatingsEnabled === 'function' ? getPresetRatingsEnabled() : true;
            const heart = L.DomUtil.create('span', 'preset-ratings-heart', label);
            heart.setAttribute('aria-hidden', 'true');
            heart.textContent = '❤';
            const span = L.DomUtil.create('span', 'preset-ratings-text', label);
            span.textContent = ' Мои оценки';
            L.DomEvent.disableClickPropagation(wrap);
            L.DomEvent.disableScrollPropagation(wrap);
            cb.addEventListener('change', function () {
                if (typeof setPresetRatingsEnabled === 'function') {
                    setPresetRatingsEnabled(cb.checked);
                }
                if (typeof refreshRatingsAfterPresetToggle === 'function') {
                    refreshRatingsAfterPresetToggle();
                }
            });
            return wrap;
        }
    });
    new PresetRatingsToggle().addTo(map);

    setMapApartmentMarkers(apartments);

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
