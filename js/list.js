/** Список квартир в сайдбаре: поиск, сортировка, рейтинги */
function getBuildYear(apt) {
    if (apt.build_year) return String(apt.build_year);
    const desc = (apt.description || '') + ' ' + (apt.title || '');
    const m = desc.match(/(\d{4})\s*года?\s*постройки|построен[а]?\s*в\s*(\d{4})|(\d{4})\s*год[а]?\s*постройки|дом[а]?\s*(\d{4})|(\d{4})\s*г\.?\s*постройки/i);
    if (m) return (m[1] || m[2] || m[3] || m[4] || m[5] || '').trim();
    const year = desc.match(/\b(19\d{2}|20\d{2})\s*год/i);
    return year ? year[1] : '';
}

function formatTitleRooms(apt) {
    const raw = apt.title || '';
    var av = raw.match(/^(\d)-к\.\s*квартир/i);
    if (av) {
        var n = parseInt(av[1], 10);
        if (n === 1) return 'Однокомнатная';
        if (n === 2) return 'Двухкомнатная';
        if (n === 3) return 'Трёхкомнатная';
        if (n >= 5) return 'Пятикомнатная';
        if (n >= 4) return 'Многокомнатная';
    }
    const t = raw.toLowerCase();
    if (/1-комн|1-комнатн|однокомнатн/.test(t)) return 'Однокомнатная';
    if (/2-комн|2-комнатн|двухкомнатн|двух комн/.test(t)) return 'Двухкомнатная';
    if (/3-комн|3-комнатн|трёхкомнатн|трехкомнатн/.test(t)) return 'Трёхкомнатная';
    if (/5-комн|5-комнатн|пятикомнатн|пяти-комн|пяти\s*комн/.test(t)) return 'Пятикомнатная';
    if (/4-комн|4-комнатн|многокомнатн/.test(t)) return 'Многокомнатная';
    return apt.title || 'Квартира';
}

function getRoomsCount(apt) {
    const raw = apt.title || '';
    var av = raw.match(/^(\d)-к\.\s*квартир/i);
    if (av) return Math.min(parseInt(av[1], 10), 5);
    const t = raw.toLowerCase();
    if (/1-комн|1-комнатн|однокомнатн/.test(t)) return 1;
    if (/2-комн|2-комнатн|двухкомнатн|двух комн/.test(t)) return 2;
    if (/3-комн|3-комнатн|трёхкомнатн|трехкомнатн/.test(t)) return 3;
    if (/5-комн|5-комнатн|пятикомнатн|пяти-комн|пяти\s*комн/.test(t)) return 5;
    if (/4-комн|4-комнатн|многокомнатн/.test(t)) return 4;
    return 0;
}

/** Номер этажа для сортировки (из "4/9" берётся 4). Нет данных → 0. */
function getFloorNumber(apt) {
    var s = (apt.floor || '').toString().trim();
    if (!s) return 0;
    var m = s.match(/^(\d+)/);
    return m ? parseInt(m[1], 10) : 0;
}

function getAptId(apt) {
    var url = apt.url || '';
    var m = url.match(/\/(\d+)\/?$/);
    return m ? m[1] : '';
}

function getCardSearchText(apt) {
    const year = getBuildYear(apt);
    const area = apt.total_area ? apt.total_area + ' м²' : '';
    const perSqm = apt.price_per_sqm != null ? String(apt.price_per_sqm) : '';
    const aptId = getAptId(apt);
    const floor = apt.floor || '';
    var srcTag = apt.source === 'avito' ? 'авито' : 'циан';
    return [apt.title, apt.price, apt.address, year, area, perSqm, aptId, floor, (apt.metro || []).join(' '), srcTag].filter(Boolean).join(' ').toLowerCase();
}

function formatPricePerSqm(value) {
    var n = parseInt(value, 10);
    if (isNaN(n)) return '';
    return n.toLocaleString('ru-RU') + ' ₽/м²';
}

/** Статистика по всему списку квартир для цветовой индикации (зелёный — лучше, красный — хуже) */
function getParamStats(apartments) {
    var years = [], areas = [], rooms = [], prices = [], perSqm = [], floors = [];
    (apartments || []).forEach(function (apt) {
        var y = parseInt(getBuildYear(apt), 10);
        if (y && y > 1900) years.push(y);
        var a = parseFloat(String(apt.total_area || '').replace(',', '.'), 10);
        if (!isNaN(a) && a > 0) areas.push(a);
        rooms.push(getRoomsCount(apt));
        var p = parseInt((apt.price || '').replace(/\D/g, ''), 10);
        if (p > 0) prices.push(p);
        if (apt.price_per_sqm != null && apt.price_per_sqm > 0) perSqm.push(Number(apt.price_per_sqm));
        var fl = getFloorNumber(apt);
        if (fl > 0) floors.push(fl);
    });
    function minMax(arr) {
        if (!arr.length) return { min: 0, max: 1 };
        return { min: Math.min.apply(null, arr), max: Math.max.apply(null, arr) };
    }
    return {
        build_year: minMax(years),
        area: minMax(areas),
        rooms: minMax(rooms),
        price: minMax(prices),
        price_per_sqm: minMax(perSqm),
        floor: floors.length ? minMax(floors) : { min: 0, max: 0 }
    };
}

/**
 * Цвет параметра в карточке: зелёный = хорошо, жёлтый = средне, красный = плохо.
 * @param {number} value - значение
 * @param {object} range - { min, max }
 * @param {boolean} higherIsBetter - true для года/площади/комнат, false для цены и цены за м²
 */
function getParamColor(value, range, higherIsBetter) {
    if (value == null || value === '' || !range || range.min === range.max) return null;
    var t = (Number(value) - range.min) / (range.max - range.min);
    if (isNaN(t)) return null;
    if (!higherIsBetter) t = 1 - t;
    if (t >= 0.66) return '#28a745';
    if (t >= 0.33) return '#ffc107';
    return '#dc3545';
}

/** 0…1: чем выше, тем лучше по параметру (как в карточках). */
function normalizeParamT(value, range, higherIsBetter) {
    if (value == null || value === '' || !range || range.min === range.max) return 0.5;
    var t = (Number(value) - range.min) / (range.max - range.min);
    if (isNaN(t)) return 0.5;
    if (!higherIsBetter) t = 1 - t;
    return Math.max(0, Math.min(1, t));
}

/** Ручная оценка 👍👎 → 0…1 (дорога закрыта = 0). */
function manualRatingToT(r) {
    if (r === 4) return 0;
    if (r === 3) return 1;
    if (r === 2) return 0.65;
    if (r === 1) return 0.35;
    return 0.5;
}

/**
 * Суммарный балл: цена, ₽/м², площадь, этаж, год, комнаты (по 1) + ручной рейтинг (вес 2).
 * Все в диапазоне 0…1 по сравнению с остальными квартирами в списке.
 */
function getCompositeScore(apt, stats) {
    stats = stats || getParamStats(window.APARTMENTS || []);
    var parts = [];
    parts.push({ w: 2, t: manualRatingToT(getRating(apt.url)) });
    var priceNum = parseInt((apt.price || '').replace(/\D/g, ''), 10) || 0;
    parts.push({ w: 1, t: normalizeParamT(priceNum, stats.price, false) });
    var perSqm = apt.price_per_sqm != null ? Number(apt.price_per_sqm) : null;
    parts.push({ w: 1, t: normalizeParamT(perSqm, stats.price_per_sqm, false) });
    var areaNum = parseFloat(String(apt.total_area || '').replace(',', '.'), 10);
    parts.push({ w: 1, t: normalizeParamT(areaNum, stats.area, true) });
    var fn = getFloorNumber(apt);
    parts.push({ w: 1, t: fn > 0 ? normalizeParamT(fn, stats.floor, true) : 0.5 });
    var yn = parseInt(getBuildYear(apt), 10) || 0;
    parts.push({ w: 1, t: yn > 1900 ? normalizeParamT(yn, stats.build_year, true) : 0.5 });
    parts.push({ w: 1, t: normalizeParamT(getRoomsCount(apt), stats.rooms, true) });
    var wsum = 0;
    var acc = 0;
    parts.forEach(function (p) {
        wsum += p.w;
        acc += p.w * p.t;
    });
    return acc / wsum;
}

/** Min/max суммарного балла по списку (для цвета маркера и сортировки). */
function getCompositeScoreRange(apartments, stats) {
    stats = stats || getParamStats(apartments || []);
    var scores = [];
    (apartments || []).forEach(function (apt) {
        scores.push(getCompositeScore(apt, stats));
    });
    if (!scores.length) return { min: 0, max: 1 };
    return { min: Math.min.apply(null, scores), max: Math.max.apply(null, scores) };
}
window.getCompositeScoreRange = getCompositeScoreRange;

/**
 * Цвет обводки маркера на карте по выбранному полю сортировки (как градация в карточке).
 * @param {object} stats — из getParamStats (передайте один раз на перерисовку маркеров).
 * @param {object} [compositeRange] — для field=composite: min/max баллов (считать один раз на кадр).
 */
function getMarkerOutlineForSortField(apt, field, stats, compositeRange) {
    stats = stats || getParamStats(window.APARTMENTS || []);
    if (field === 'rating') {
        var r = getRating(apt.url);
        if (r === 4) return '#4b5563';
        if (r === 3) return '#155724';
        if (r === 2) return '#b38600';
        if (r === 1) return '#921925';
        return '#f8f9fa';
    }
    var c = null;
    if (field === 'price') {
        var priceNum = parseInt((apt.price || '').replace(/\D/g, ''), 10) || 0;
        c = getParamColor(priceNum, stats.price, false);
    } else if (field === 'price_per_sqm') {
        var perSqm = apt.price_per_sqm != null ? Number(apt.price_per_sqm) : null;
        c = getParamColor(perSqm, stats.price_per_sqm, false);
    } else if (field === 'area') {
        var areaNum = parseFloat(String(apt.total_area || '').replace(',', '.'), 10);
        c = getParamColor(areaNum, stats.area, true);
    } else if (field === 'floor') {
        var fn = getFloorNumber(apt);
        c = fn > 0 ? getParamColor(fn, stats.floor, true) : null;
    } else if (field === 'build_year') {
        var yn = parseInt(getBuildYear(apt), 10) || 0;
        c = getParamColor(yn, stats.build_year, true);
    } else if (field === 'rooms') {
        c = getParamColor(getRoomsCount(apt), stats.rooms, true);
    } else if (field === 'composite') {
        var range = compositeRange || getCompositeScoreRange(window.APARTMENTS || [], stats);
        var score = getCompositeScore(apt, stats);
        c = getParamColor(score, range, true);
    }
    return c || '#ffffff';
}
window.getMarkerOutlineForSortField = getMarkerOutlineForSortField;

function sortApartments(sortValue) {
    var parts = (sortValue || 'rating-desc').split('-');
    var field = parts[0];
    var dir = parts[1] === 'asc' ? 1 : -1;
    var apartments = window.APARTMENTS || [];
    var sorted = apartments.slice();

    function num(a, b, getVal) {
        var va = getVal(a);
        var vb = getVal(b);
        if (va < vb) return -1 * dir;
        if (va > vb) return 1 * dir;
        return 0;
    }
    function str(a, b, getVal) {
        var va = (getVal(a) || '').toString();
        var vb = (getVal(b) || '').toString();
        var c = va.localeCompare(vb);
        return c * dir;
    }

    if (field === 'rating') {
        sorted.sort(function (a, b) {
            var oa = getRatingSortOrder(getRating(a.url));
            var ob = getRatingSortOrder(getRating(b.url));
            return (oa - ob) * dir || (a.title || '').localeCompare(b.title || '');
        });
    } else if (field === 'price') {
        sorted.sort(function (a, b) {
            return num(a, b, function (x) { return parseInt((x.price || '').replace(/\D/g, ''), 10) || 0; });
        });
    } else if (field === 'price_per_sqm') {
        sorted.sort(function (a, b) {
            return num(a, b, function (x) { return (x.price_per_sqm != null ? Number(x.price_per_sqm) : 0); });
        });
    } else if (field === 'area') {
        sorted.sort(function (a, b) {
            return num(a, b, function (x) { return (x.total_area != null ? parseFloat(String(x.total_area).replace(',', '.'), 10) : 0); });
        });
    } else if (field === 'floor') {
        sorted.sort(function (a, b) {
            return num(a, b, getFloorNumber) || (a.title || '').localeCompare(b.title || '');
        });
    } else if (field === 'build_year') {
        sorted.sort(function (a, b) {
            var ya = parseInt(getBuildYear(a), 10) || 0;
            var yb = parseInt(getBuildYear(b), 10) || 0;
            return (ya - yb) * dir || (a.title || '').localeCompare(b.title || '');
        });
    } else if (field === 'rooms') {
        sorted.sort(function (a, b) {
            return num(a, b, getRoomsCount) || (a.title || '').localeCompare(b.title || '');
        });
    } else if (field === 'composite') {
        var stComp = getParamStats(apartments);
        sorted.sort(function (a, b) {
            var sa = getCompositeScore(a, stComp);
            var sb = getCompositeScore(b, stComp);
            if (sa < sb) return -1 * dir;
            if (sa > sb) return 1 * dir;
            return (a.title || '').localeCompare(b.title || '');
        });
    }
    applyListFilter(sorted);
    scheduleSyncMapMarkerOutlines();
}

/** Сразу после смены сортировки обновить обводку маркеров на карте (без перезагрузки страницы). */
function scheduleSyncMapMarkerOutlines() {
    function run() {
        var fn = typeof syncMapMarkerOutlines === 'function'
            ? syncMapMarkerOutlines
            : (typeof window !== 'undefined' && typeof window.syncMapMarkerOutlines === 'function'
                ? window.syncMapMarkerOutlines
                : null);
        if (fn) fn();
    }
    setTimeout(run, 0);
}

var ROOMS_FILTER_STORAGE_KEY = 'cian_rooms_visible';

function mapAptToRoomFilterKey(apt) {
    var n = getRoomsCount(apt);
    if (n === 0) return '0';
    if (n >= 4) return '4';
    return String(n);
}

function getDefaultRoomFilterState() {
    return { '0': true, '1': true, '2': true, '3': true, '4': true };
}

function getRoomFilterState() {
    try {
        var s = localStorage.getItem(ROOMS_FILTER_STORAGE_KEY);
        if (s) {
            var o = JSON.parse(s);
            var def = getDefaultRoomFilterState();
            Object.keys(def).forEach(function (k) {
                if (typeof o[k] === 'undefined') o[k] = def[k];
            });
            return o;
        }
    } catch (e) {}
    return getDefaultRoomFilterState();
}

function saveRoomFilterStateFromDom() {
    var wrap = document.getElementById('rooms-filter');
    if (!wrap) return;
    var o = {};
    wrap.querySelectorAll('input[type="checkbox"][data-rooms]').forEach(function (cb) {
        o[cb.getAttribute('data-rooms')] = cb.checked;
    });
    try {
        localStorage.setItem(ROOMS_FILTER_STORAGE_KEY, JSON.stringify(o));
    } catch (e) {}
}

function apartmentMatchesRoomFilter(apt) {
    var key = mapAptToRoomFilterKey(apt);
    return getRoomFilterState()[key] === true;
}

function filterApartmentsByRooms(apartments) {
    return (apartments || []).filter(apartmentMatchesRoomFilter);
}

function onRoomsFilterChanged() {
    saveRoomFilterStateFromDom();
    var pool = window.APARTMENTS || [];
    if (typeof setMapApartmentMarkers === 'function') {
        setMapApartmentMarkers(filterApartmentsByRooms(pool));
    }
    applyListFilter(window._lastSortedApartments || pool.slice());
}

function syncRoomsFilterCheckboxesFromStorage() {
    var wrap = document.getElementById('rooms-filter');
    if (!wrap) return;
    var state = getRoomFilterState();
    wrap.querySelectorAll('input[type="checkbox"][data-rooms]').forEach(function (cb) {
        var k = cb.getAttribute('data-rooms');
        cb.checked = state[k] !== false;
    });
}

function initRoomsFilter() {
    var wrap = document.getElementById('rooms-filter');
    if (!wrap) return;
    syncRoomsFilterCheckboxesFromStorage();
    wrap.querySelectorAll('input[type="checkbox"][data-rooms]').forEach(function (cb) {
        cb.addEventListener('change', onRoomsFilterChanged);
    });
}

function applyListFilter(sortedApartments) {
    window._lastSortedApartments = sortedApartments;
    var query = (document.getElementById('list-search-input').value || '').trim().toLowerCase();
    var list = query
        ? sortedApartments.filter(function (apt) { return getCardSearchText(apt).indexOf(query) !== -1; })
        : sortedApartments.slice();
    list = list.filter(apartmentMatchesRoomFilter);
    renderList(list, list.length);
}

function renderList(apartmentsToRender, totalCount) {
    const cardsContainer = document.getElementById('list-cards');
    const sortControls = document.querySelector('.sort-controls');
    if (!cardsContainer) return;
    cardsContainer.innerHTML = '';
    totalCount = totalCount !== undefined ? totalCount : apartmentsToRender.length;

    var fullList = window.APARTMENTS || [];
    var stats = getParamStats(fullList);

    apartmentsToRender.forEach(function (apt, index) {
        const rating = getRating(apt.url);
        const photos = (apt.photos && apt.photos.length) ? apt.photos : (apt.img_src ? [apt.img_src] : []);
        const imgSrc = apt.img_src || (photos[0] || '');

        var buildYearNum = parseInt(getBuildYear(apt), 10);
        var areaNum = parseFloat(String(apt.total_area || '').replace(',', '.'), 10);
        var roomsNum = getRoomsCount(apt);
        var priceNum = parseInt((apt.price || '').replace(/\D/g, ''), 10) || 0;
        var perSqmNum = apt.price_per_sqm != null ? Number(apt.price_per_sqm) : null;

        var colorYear = getParamColor(buildYearNum, stats.build_year, true);
        var colorArea = getParamColor(areaNum, stats.area, true);
        var colorRooms = getParamColor(roomsNum, stats.rooms, true);
        var colorPrice = getParamColor(priceNum, stats.price, false);
        var colorPerSqm = getParamColor(perSqmNum, stats.price_per_sqm, false);
        var floorNum = getFloorNumber(apt);
        var colorFloor = floorNum > 0 ? getParamColor(floorNum, stats.floor, true) : null;

        const div = document.createElement('div');
        div.className = 'apartment' + (isRatingClosed(rating) ? ' rating-closed' : '');
        div.id = 'apartment-' + index;
        div.dataset.url = apt.url;

        let imgHtml = '';
        if (imgSrc) {
            imgHtml = '<div class="preview-wrap"><img src="' + imgSrc + '" alt="' + (apt.title || '').replace(/"/g, '&quot;') + '"></div>';
        }

        const num = index + 1;
        const buildYear = getBuildYear(apt);
        const titleRooms = formatTitleRooms(apt);
        const areaStr = apt.total_area ? ', ' + apt.total_area + ' м²' : '';
        const floorStr = apt.floor ? ', этаж ' + apt.floor : '';
        const pricePerSqm = apt.price_per_sqm != null ? formatPricePerSqm(apt.price_per_sqm) : '';
        const aptId = getAptId(apt);
        var listingLabel = (apt.source === 'avito') ? 'Авито' : 'Циан';
        var linkSourceClass = (apt.source === 'avito')
            ? 'btn-cian-card btn-listing-source btn-avito-card'
            : 'btn-cian-card btn-listing-source';

        var styleYear = colorYear ? ' style="color:' + colorYear + '"' : '';
        var styleArea = colorArea ? ' style="color:' + colorArea + '"' : '';
        var styleRooms = colorRooms ? ' style="color:' + colorRooms + '"' : '';
        var stylePrice = colorPrice ? ' style="color:' + colorPrice + '"' : '';
        var stylePerSqm = colorPerSqm ? ' style="color:' + colorPerSqm + '"' : '';
        var styleFloor = colorFloor ? ' style="color:' + colorFloor + '"' : '';

        div.innerHTML = '<div class="card-top-line">' +
            '<span class="card-index">' + num + ' из ' + totalCount + '</span>' +
            (aptId ? '<span class="card-apt-id">Код ' + aptId.replace(/</g, '&lt;') + '</span>' : '') +
            '</div>' +
            imgHtml +
            '<h3 class="card-title-rooms">' +
            '<span class="card-rooms"' + styleRooms + '>' + titleRooms.replace(/</g, '&lt;') + '</span>' +
            (areaStr ? '<span class="card-area"' + styleArea + '>' + areaStr.replace(/</g, '&lt;') + '</span>' : '') +
            (floorStr ? '<span class="card-floor"' + styleFloor + '>' + floorStr.replace(/</g, '&lt;') + '</span>' : '') +
            (buildYear ? '<span class="card-build-year-right"' + styleYear + '>Год: ' + buildYear + '</span>' : '') +
            '</h3>' +
            '<div class="card-price-line">' +
            '<span class="price"' + stylePrice + '>' + (apt.price || '').replace(/</g, '&lt;') + '</span>' +
            (buildYear ? '<span class="build-year"' + styleYear + '>Год: ' + buildYear + '</span>' : '') +
            (pricePerSqm ? '<span class="card-price-per-sqm"' + stylePerSqm + '>' + pricePerSqm + '</span>' : '') +
            '</div>' +
            '<p class="address">' + (apt.address || '').replace(/</g, '&lt;') + '</p>' +
            '<div class="card-rating-row">' +
            '<div class="rating-buttons">' +
            '<button class="rating-btn green ' + (rating === 3 ? 'active' : '') + '" data-rating="3" data-url="' + apt.url + '">👍</button>' +
            '<button class="rating-btn yellow ' + (rating === 2 ? 'active' : '') + '" data-rating="2" data-url="' + apt.url + '">😐</button>' +
            '<button class="rating-btn red ' + (rating === 1 ? 'active' : '') + '" data-rating="1" data-url="' + apt.url + '">👎</button>' +
            '<button class="rating-btn closed ' + (rating === 4 ? 'active' : '') + '" data-rating="4" data-url="' + apt.url + '" title="Дорога закрыта">🚫</button>' +
            '</div>' +
            '<span class="rating-info" style="color:' + getRatingColor(rating) + '">' + getRatingText(rating) + '</span>' +
            '<a class="' + linkSourceClass + '" href="' + (apt.url || '#').replace(/"/g, '&quot;') + '" target="_blank" rel="noopener">' + listingLabel + '</a>' +
            '</div>';

        const wrap = div.querySelector('.preview-wrap');
        if (wrap) wrap.addEventListener('click', function (e) { e.stopPropagation(); openGallery(apt, 0); });
        div.querySelectorAll('.rating-btn').forEach(function (btn) {
            btn.addEventListener('click', function (e) {
                e.stopPropagation();
                const r = parseInt(btn.dataset.rating, 10);
                const currentRating = getRating(apt.url);
                const newRating = (currentRating === r) ? 0 : r;
                setRating(apt.url, newRating);
                div.querySelector('.rating-info').textContent = getRatingText(newRating);
                div.querySelector('.rating-info').style.color = getRatingColor(newRating);
                div.querySelectorAll('.rating-btn').forEach(function (b) { b.classList.remove('active'); });
                if (newRating !== 0) btn.classList.add('active');
                div.classList.toggle('rating-closed', isRatingClosed(newRating));
                var sel = document.getElementById('list-sort-select');
                if (sel && (sel.value.indexOf('rating') === 0 || sel.value.indexOf('composite') === 0)) sortApartments(sel.value);
                else applyListFilter(window._lastSortedApartments || []);
                updateMarkerIcon(apt, newRating);
            });
        });

        div.addEventListener('click', function (e) {
            if (e.target.closest('.preview-wrap') || e.target.closest('.rating-btn') || e.target.closest('.btn-listing-source')) return;
            if (rating === 4) {
                e.preventDefault();
                setRating(apt.url, 0);
                div.querySelector('.rating-info').textContent = getRatingText(0);
                div.querySelector('.rating-info').style.color = getRatingColor(0);
                div.querySelectorAll('.rating-btn').forEach(function (b) { b.classList.remove('active'); });
                div.classList.remove('rating-closed');
                updateMarkerIcon(apt, 0);
                var sel = document.getElementById('list-sort-select');
                if (sel && (sel.value.indexOf('rating') === 0 || sel.value.indexOf('composite') === 0)) sortApartments(sel.value);
                else applyListFilter(window._lastSortedApartments || []);
                return;
            }
            map.setView([apt.lat, apt.lon], 16);
            const m = markers.find(function (mr) { return mr._apt && mr._apt.url === apt.url; });
            if (m) m.openPopup();
            document.querySelectorAll('.apartment').forEach(function (el) { el.classList.remove('highlighted'); });
            div.classList.add('highlighted');
            div.scrollIntoView({ behavior: 'smooth', block: 'center' });
        });

        cardsContainer.appendChild(div);
    });

    // Не перезаписываем _lastSortedApartments — он хранит полный отсортированный список;
    // фильтр по тексту применяется только в applyListFilter.
}

function initList() {
    const apartments = window.APARTMENTS || [];
    window._lastSortedApartments = apartments;

    var searchInput = document.getElementById('list-search-input');
    var searchClear = document.getElementById('list-search-clear');
    if (searchInput) {
        searchInput.addEventListener('input', function () { applyListFilter(window._lastSortedApartments || []); });
        searchInput.addEventListener('keyup', function () { applyListFilter(window._lastSortedApartments || []); });
    }
    if (searchClear) {
        searchClear.addEventListener('click', function () {
            if (searchInput) searchInput.value = '';
            applyListFilter(window._lastSortedApartments || []);
            if (searchInput) searchInput.focus();
        });
    }

    var sortSelect = document.getElementById('list-sort-select');
    if (sortSelect) {
        sortSelect.addEventListener('change', function () {
            sortApartments(sortSelect.value);
        });
    }

    sortApartments(sortSelect ? sortSelect.value : 'rating-desc');
    initRoomsFilter();
}
