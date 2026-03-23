/**
 * Копирование ID квартир по оценке (localStorage) — для вставки в data/hidden_ids.js.
 * Циан: sale/flat/id. Авито: avito_id или …_id в URL — те же строки в NEWLY_HIDDEN_IDS скрывают объявления на карте.
 */
(function () {
    function getCianFlatIdForCopy(apt) {
        var u = apt.url || '';
        var m = u.match(/sale\/flat\/(\d+)/);
        return m ? m[1] : null;
    }

    function getAvitoItemIdForCopy(apt) {
        if (apt.avito_id) return String(apt.avito_id);
        var u = apt.url || '';
        if (u.indexOf('avito.') === -1 && apt.source !== 'avito') return null;
        var m = u.match(/_(\d+)(?:\?.*)?$/);
        return m ? m[1] : null;
    }

    function collectByRating(ratingValue, apartmentsAll) {
        var cian = [];
        var avito = [];
        (apartmentsAll || []).forEach(function (apt) {
            if (!apt || !apt.url) return;
            if (getRating(apt.url) !== ratingValue) return;
            var cid = getCianFlatIdForCopy(apt);
            if (cid) cian.push(cid);
            var aid = getAvitoItemIdForCopy(apt);
            if (aid) avito.push(aid);
        });
        function uniq(arr) {
            var s = {};
            var o = [];
            arr.forEach(function (x) {
                if (!s[x]) {
                    s[x] = 1;
                    o.push(x);
                }
            });
            return o;
        }
        return { cian: uniq(cian), avito: uniq(avito) };
    }

    function buildClipboardText(data) {
        var seen = {};
        var merged = [];
        data.cian.concat(data.avito).forEach(function (id) {
            if (id && !seen[id]) {
                seen[id] = 1;
                merged.push(id);
            }
        });
        if (!merged.length) return '';
        return merged
            .map(function (id) {
                return "'" + id + "'";
            })
            .join(',');
    }

    function showFeedback(msg) {
        var el = document.getElementById('copy-rating-feedback');
        if (!el) return;
        el.textContent = msg;
        clearTimeout(el._copyRatingT);
        el._copyRatingT = setTimeout(function () {
            el.textContent = '';
        }, 2800);
    }

    function copyText(text) {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            return navigator.clipboard.writeText(text);
        }
        return new Promise(function (resolve, reject) {
            var ta = document.createElement('textarea');
            ta.value = text;
            ta.setAttribute('readonly', '');
            ta.style.position = 'fixed';
            ta.style.left = '-9999px';
            document.body.appendChild(ta);
            ta.select();
            try {
                if (document.execCommand('copy')) resolve();
                else reject(new Error('execCommand'));
            } catch (e) {
                reject(e);
            }
            document.body.removeChild(ta);
        });
    }

    function copyForRating(ratingValue, label) {
        var all = window.APARTMENTS_ALL || window.APARTMENTS || [];
        var data = collectByRating(ratingValue, all);
        if (!data.cian.length && !data.avito.length) {
            showFeedback('Нет квартир с оценкой «' + label + '»');
            return;
        }
        var text = buildClipboardText(data);
        copyText(text)
            .then(function () {
                var parts = [];
                if (data.cian.length) parts.push('Циан: ' + data.cian.length);
                if (data.avito.length) parts.push('Авито: ' + data.avito.length);
                showFeedback('Скопировано — ' + parts.join(', '));
            })
            .catch(function () {
                showFeedback('Не удалось скопировать (браузер)');
            });
    }

    window.initCopyRatingIdsToolbar = function () {
        var mapBtn = {
            'copy-rating-3': { r: 3, l: 'Отлично' },
            'copy-rating-2': { r: 2, l: 'Хорошо' },
            'copy-rating-1': { r: 1, l: 'Плохо' },
            'copy-rating-4': { r: 4, l: 'Дорога закрыта' }
        };
        Object.keys(mapBtn).forEach(function (id) {
            var btn = document.getElementById(id);
            if (!btn) return;
            btn.addEventListener('click', function () {
                copyForRating(mapBtn[id].r, mapBtn[id].l);
            });
        });
    };
})();
