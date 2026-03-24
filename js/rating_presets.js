/**
 * Предустановленные оценки для гостей сайта (пока включён чекбокс «Мои оценки»).
 * Приоритетные ID — 👍 (3), все остальные квартиры из данных — 😐 (2).
 * Циан: id из sale/flat/<id>. Авито: avito_id или …_<id> в URL.
 */
window.RATING_PRESET_PRIORITY_IDS = [
    '322494601',
    '327734707',
    '327663356',
    '7674493053',
    '7655163507',
    '7971674555'
];

/**
 * @param {object[]} apartments — полный список из apartments.js (до фильтра видимости).
 * @returns {Object.<string, number>} url → 3 или 2
 */
function buildRatingPresetByUrl(apartments) {
    var pri = {};
    (window.RATING_PRESET_PRIORITY_IDS || []).forEach(function (id) {
        pri[String(id)] = true;
    });
    var map = {};
    (apartments || []).forEach(function (apt) {
        var url = apt && apt.url;
        if (!url) return;
        var u = String(url);
        var id = null;
        if (u.indexOf('cian.ru') !== -1) {
            var mc = u.match(/sale\/flat\/(\d+)/);
            if (mc) id = mc[1];
        }
        if (apt.source === 'avito' || u.indexOf('avito.') !== -1) {
            if (apt.avito_id != null && apt.avito_id !== '') {
                id = String(apt.avito_id);
            } else {
                var clean = u.split('?')[0].replace(/\/+$/, '');
                var ma = clean.match(/_(\d+)$/);
                if (ma) id = ma[1];
            }
        }
        if (!id) return;
        map[url] = pri[id] ? 3 : 2;
    });
    return map;
}

window.buildRatingPresetByUrl = buildRatingPresetByUrl;
