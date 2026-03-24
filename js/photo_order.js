/**
 * Порядок фото: для указанных объявлений Циан выбранное изображение (схема) — первое в photos и в img_src.
 * Ключ — id из URL /sale/flat/ID, значение — уникальный фрагмент пути/имени файла.
 */
(function () {
    var FLOORPLAN_FIRST = {
        '322494601': '2652355942-1.jpg',
        '327734707': '2827405357-1.jpg',
        '327663356': '2825770488-1.jpg',
        '327963650': '2833950092-1.jpg',
        '326748976': '2802172103-1.jpg',
        '324934151': '2733295197-1.jpg',
        '326549828': '2795349842-1.jpg',
        '324889160': '2736271928-1.jpg',
        '313818809': '2404131734-1.jpg'
    };

    function cianFlatId(url) {
        if (!url || url.indexOf('cian.ru') === -1) return null;
        var m = String(url).match(/sale\/flat\/(\d+)/);
        return m ? m[1] : null;
    }

    function applyPreferredPhotoOrder(apartments) {
        (apartments || []).forEach(function (apt) {
            var id = cianFlatId(apt.url);
            if (!id) return;
            var needle = FLOORPLAN_FIRST[id];
            if (!needle) return;
            var photos = apt.photos;
            if (!photos || !photos.length) return;
            var idx = -1;
            for (var i = 0; i < photos.length; i++) {
                if (photos[i].indexOf(needle) !== -1) {
                    idx = i;
                    break;
                }
            }
            if (idx <= 0) return;
            var moved = photos.splice(idx, 1)[0];
            photos.unshift(moved);
            apt.img_src = moved;
        });
    }

    window.applyPreferredPhotoOrder = applyPreferredPhotoOrder;
})();
