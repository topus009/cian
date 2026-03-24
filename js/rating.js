/** Рейтинги квартир в localStorage. 3=Отлично, 2=Хорошо, 1=Плохо, 4=Дорога закрыта */
const RATING_KEY = 'cian_apartment_ratings';
/** Состояние чекбокса «Мои оценки»: надёжно в localStorage (cookie на file:// часто не пишется). */
const PRESET_TOGGLE_STORAGE_KEY = 'cian_use_preset_ratings';
/** Дублирование в cookie для HTTP-сайтов (опционально). */
const PRESET_RATINGS_COOKIE = 'cian_preset_ratings';

function getRatingStored(url) {
    const r = JSON.parse(localStorage.getItem(RATING_KEY) || '{}');
    return Object.prototype.hasOwnProperty.call(r, url) ? r[url] : undefined;
}

/**
 * Чекбокс «Мои оценки» включён → приоритет у предустановок (код), не у localStorage.
 * Выключен → только оценки из хранилища браузера.
 */
function getRating(url) {
    if (getPresetRatingsEnabled() && window.RATING_PRESET_BY_URL && window.RATING_PRESET_BY_URL[url] != null) {
        return window.RATING_PRESET_BY_URL[url];
    }
    const s = getRatingStored(url);
    if (s !== undefined) return s;
    return 0;
}

function setRating(url, rating) {
    const r = JSON.parse(localStorage.getItem(RATING_KEY) || '{}');
    r[url] = rating;
    localStorage.setItem(RATING_KEY, JSON.stringify(r));
}

function getRatingText(r) {
    return { 3: 'Отлично', 2: 'Хорошо', 1: 'Плохо', 4: 'Дорога закрыта' }[r] || 'Не оценено';
}
function getRatingColor(r) {
    return { 3: '#28a745', 2: '#ffc107', 1: '#dc3545', 4: '#9ca3af' }[r] || '#6c757d';
}
/** Для сортировки: «Дорога закрыта» (4) в конец. Возвращает порядок: 3>2>1>0(нет)>4(закрыта) */
function getRatingSortOrder(r) {
    return { 3: 4, 2: 3, 1: 2, 0: 1, 4: 0 }[r] ?? 1;
}
/** true, если рейтинг «Дорога закрыта» */
function isRatingClosed(r) {
    return r === 4;
}

function getPresetRatingsEnabled() {
    try {
        var v = localStorage.getItem(PRESET_TOGGLE_STORAGE_KEY);
        if (v === '0') return false;
        if (v === '1') return true;
    } catch (e) {}
    var m = document.cookie.match(new RegExp('(?:^|;\\s*)' + PRESET_RATINGS_COOKIE + '=(0|1)'));
    if (m) {
        var fromCookie = m[1] === '1';
        try {
            localStorage.setItem(PRESET_TOGGLE_STORAGE_KEY, fromCookie ? '1' : '0');
        } catch (e2) {}
        return fromCookie;
    }
    return true;
}

function setPresetRatingsEnabled(on) {
    try {
        localStorage.setItem(PRESET_TOGGLE_STORAGE_KEY, on ? '1' : '0');
    } catch (e) {}
    try {
        document.cookie =
            PRESET_RATINGS_COOKIE +
            '=' +
            (on ? '1' : '0') +
            ';path=/;max-age=31536000;SameSite=Lax';
    } catch (e2) {}
}

function refreshRatingsAfterPresetToggle() {
    function redrawMapMarkers() {
        if (typeof window.refreshMapMarkersForCurrentFilter === 'function') {
            window.refreshMapMarkersForCurrentFilter();
        } else if (typeof syncMapMarkerOutlines === 'function') {
            syncMapMarkerOutlines();
        }
    }
    /* Сначала карта — сразу новые цвета маркеров, потом список */
    redrawMapMarkers();
    var sel = document.getElementById('list-sort-select');
    if (sel && typeof sortApartments === 'function') {
        sortApartments(sel.value);
    } else if (typeof applyListFilter === 'function' && window._lastSortedApartments) {
        applyListFilter(window._lastSortedApartments);
    }
    redrawMapMarkers();
    requestAnimationFrame(redrawMapMarkers);
}

window.getRatingStored = getRatingStored;
window.getPresetRatingsEnabled = getPresetRatingsEnabled;
window.setPresetRatingsEnabled = setPresetRatingsEnabled;
window.refreshRatingsAfterPresetToggle = refreshRatingsAfterPresetToggle;
