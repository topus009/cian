# -*- coding: utf-8 -*-
"""
Читает apartments.json, добавляет небольшой разброс координат при дубликатах,
генерирует map_cian.html — карта избранных квартир Циан (Leaflet + сайдбар + слайдер по клику).
"""
import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(SCRIPT_DIR, 'apartments.json')
OUT_HTML = os.path.join(SCRIPT_DIR, 'map_cian.html')


def jitter_coords(apartments):
    """Добавляет небольшой разброс к одинаковым координатам, чтобы маркеры не слипались."""
    from collections import defaultdict
    by_key = defaultdict(list)
    for i, apt in enumerate(apartments):
        key = (apt.get('lat'), apt.get('lon'))
        by_key[key].append(i)

    for (lat, lon), indices in by_key.items():
        if lat is None or lon is None:
            continue
        if len(indices) <= 1:
            continue
        # Разбрасываем по маленькому радиусу (~100–200 м)
        import math
        for k, idx in enumerate(indices):
            angle = 2 * math.pi * k / len(indices)
            offset = 0.002  # ~200 м
            apartments[idx]['lat'] = lat + offset * math.cos(angle)
            apartments[idx]['lon'] = lon + offset * math.sin(angle)
    return apartments


def main():
    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        apartments = json.load(f)

    apartments = jitter_coords(apartments)
    apartments_json = json.dumps(apartments, ensure_ascii=False)

    html = '''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Избранные квартиры Циан — Санкт-Петербург</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.7.1/dist/leaflet.css">
    <style>
        * { box-sizing: border-box; }
        body { font-family: Arial, sans-serif; margin: 0; padding: 0; display: flex; }
        #map { height: 100vh; width: calc(100% - 380px); }
        #list {
            width: 380px; height: 100vh; overflow-y: auto;
            background: #f8f9fa; border-left: 1px solid #dee2e6;
        }
        .apartment {
            border-bottom: 1px solid #dee2e6; padding: 12px;
            cursor: pointer; background: #fff; margin: 8px; border-radius: 6px;
        }
        .apartment:hover { background: #f0f4f8; }
        .apartment.highlighted { background: #fff3cd; border: 2px solid #ffc107; }
        .apartment .preview-wrap { position: relative; margin-bottom: 8px; border-radius: 4px; overflow: hidden; }
        .apartment .preview-wrap img {
            width: 100%; height: 180px; object-fit: cover; display: block;
        }
        .apartment .preview-wrap::after {
            content: "\\1F50D Показать все фото"; position: absolute;
            bottom: 0; left: 0; right: 0; padding: 6px; background: rgba(0,0,0,0.6);
            color: #fff; font-size: 12px; text-align: center;
        }
        .apartment h3 { margin: 0 0 6px 0; font-size: 15px; line-height: 1.3; }
        .apartment .price { font-weight: bold; color: #0468FF; font-size: 16px; margin-bottom: 4px; }
        .apartment .address { color: #666; font-size: 12px; margin: 0; }
        .apartment .metro { color: #555; font-size: 11px; margin-top: 4px; }
        .rating-buttons { margin-top: 8px; display: flex; gap: 6px; }
        .rating-btn { padding: 4px 10px; border: none; border-radius: 4px; cursor: pointer; font-size: 12px; }
        .rating-btn.green { background: #d4edda; color: #155724; }
        .rating-btn.green.active { background: #28a745; color: white; }
        .rating-btn.yellow { background: #fff3cd; color: #856404; }
        .rating-btn.yellow.active { background: #ffc107; color: #212529; }
        .rating-btn.red { background: #f8d7da; color: #721c24; }
        .rating-btn.red.active { background: #dc3545; color: white; }
        .rating-info { font-size: 11px; color: #666; margin-top: 4px; }
        .sort-controls { padding: 10px; background: #fff; border-bottom: 1px solid #dee2e6; }
        .sort-btn { padding: 6px 12px; margin-right: 6px; border: 1px solid #dee2e6; background: #fff; cursor: pointer; border-radius: 4px; }
        .sort-btn.active { background: #0468FF; color: white; border-color: #0468FF; }
        .custom-marker { background: transparent; border: none; }
        .custom-marker div { transition: transform 0.2s; }
        .custom-marker div:hover { transform: scale(1.15); }

        /* Модальное окно: фикс-хедер, 80% слайдер, справа сайдбар с описанием */
        #gallery-modal {
            display: none; position: fixed; z-index: 9999; left: 0; top: 0; width: 100%; height: 100%;
            background: rgba(0,0,0,0.95); color: #fff; flex-direction: column;
        }
        #gallery-modal.show { display: flex; }
        #gallery-modal .modal-header {
            flex-shrink: 0; display: flex; justify-content: space-between; align-items: center; padding: 10px 16px;
            background: #111; border-bottom: 1px solid #333;
        }
        #gallery-modal .modal-title { font-size: 16px; }
        #gallery-modal .modal-close {
            background: #333; color: #fff; border: none; padding: 6px 14px; cursor: pointer; border-radius: 4px; font-size: 13px;
        }
        #gallery-modal .modal-close:hover { background: #555; }
        #gallery-modal .modal-body {
            flex: 1; display: flex; min-height: 0; overflow: hidden;
        }
        #gallery-slider-wrap {
            flex: 0 0 80%; display: flex; flex-direction: column; min-width: 0; min-height: 0; padding: 0;
        }
        #gallery-slider { flex: 1; display: flex; flex-direction: column; min-height: 0; width: 100%; }
        #gallery-slider .slider-img-wrap {
            flex: 1; min-height: 0; width: 100%; height: 100%; position: relative;
        }
        #gallery-slider .slider-img-wrap img {
            position: absolute; left: 0; top: 0; width: 100%; height: 100%; object-fit: contain; border-radius: 0;
        }
        #gallery-slider .slider-nav {
            flex-shrink: 0; display: flex; justify-content: center; gap: 10px; align-items: center; padding: 8px;
            background: #111; border-top: 1px solid #333;
        }
        #gallery-slider .slider-nav button {
            background: #333; color: #fff; border: none; padding: 8px 16px; cursor: pointer; border-radius: 4px; font-size: 12px;
        }
        #gallery-slider .slider-counter { font-size: 12px; color: #aaa; }
        #gallery-modal .modal-sidebar {
            flex: 0 0 20%; min-width: 200px; max-width: 320px; padding: 12px; background: #1a1a1a; border-left: 1px solid #333;
            display: flex; flex-direction: column; overflow: hidden;
        }
        #gallery-modal .modal-description {
            flex: 1; overflow-y: auto; font-size: 11px; line-height: 1.45; color: #bbb; white-space: pre-wrap; margin-bottom: 10px;
        }
        #gallery-modal .modal-link {
            flex-shrink: 0; display: block; text-align: center; padding: 8px 12px; background: #0468FF; color: #fff; text-decoration: none; border-radius: 4px; font-size: 12px;
        }
        #gallery-modal .modal-link:hover { background: #0356d0; }
    </style>
</head>
<body>
    <div id="map"></div>
    <div id="list">
        <div class="sort-controls">
            <button class="sort-btn active" data-sort="rating">По рейтингу</button>
            <button class="sort-btn" data-sort="price">По цене</button>
            <button class="sort-btn" data-sort="default">По умолчанию</button>
        </div>
    </div>

    <div id="gallery-modal">
        <div class="modal-header">
            <span class="modal-title" id="gallery-title"></span>
            <button class="modal-close" id="gallery-close">Закрыть</button>
        </div>
        <div class="modal-body">
            <div id="gallery-slider-wrap">
                <div id="gallery-slider">
                    <div class="slider-img-wrap"><img id="gallery-img" src="" alt=""></div>
                    <div class="slider-nav">
                        <button type="button" id="gallery-prev">← Назад</button>
                        <span class="slider-counter" id="gallery-counter">1 / 1</span>
                        <button type="button" id="gallery-next">Вперёд →</button>
                    </div>
                </div>
            </div>
            <div class="modal-sidebar">
                <div class="modal-description" id="gallery-description"></div>
                <a id="gallery-link" class="modal-link" href="#" target="_blank">Открыть на Циан</a>
            </div>
        </div>
    </div>

    <script src="https://unpkg.com/leaflet@1.7.1/dist/leaflet.js"></script>
    <script>
        const apartments = ''' + apartments_json + ''';

        const RATING_KEY = 'cian_apartment_ratings';

        function getRating(url) {
            const r = JSON.parse(localStorage.getItem(RATING_KEY) || '{}');
            return r[url] || 0;
        }
        function setRating(url, rating) {
            const r = JSON.parse(localStorage.getItem(RATING_KEY) || '{}');
            r[url] = rating;
            localStorage.setItem(RATING_KEY, JSON.stringify(r));
        }
        function getRatingText(r) {
            return { 3: 'Отлично', 2: 'Хорошо', 1: 'Плохо' }[r] || 'Не оценено';
        }
        function getRatingColor(r) {
            return { 3: '#28a745', 2: '#ffc107', 1: '#dc3545' }[r] || '#6c757d';
        }

        let currentGalleryApt = null;
        let currentPhotoIdx = 0;

        function openGallery(apt, photoIndex) {
            currentGalleryApt = apt;
            const photos = (apt.photos && apt.photos.length) ? apt.photos : (apt.img_src ? [apt.img_src] : []);
            currentPhotoIdx = photoIndex || 0;
            if (photos.length === 0) return;

            document.getElementById('gallery-title').textContent = apt.title;
            document.getElementById('gallery-description').textContent = apt.description || '';
            document.getElementById('gallery-link').href = apt.url;
            document.getElementById('gallery-modal').classList.add('show');
            showGalleryPhoto(photos, currentPhotoIdx);
        }

        function showGalleryPhoto(photos, idx) {
            const img = document.getElementById('gallery-img');
            const counter = document.getElementById('gallery-counter');
            img.src = photos[idx] || '';
            img.alt = currentGalleryApt.title;
            counter.textContent = (idx + 1) + ' / ' + photos.length;
            document.getElementById('gallery-prev').style.visibility = photos.length > 1 ? 'visible' : 'hidden';
            document.getElementById('gallery-next').style.visibility = photos.length > 1 ? 'visible' : 'hidden';
        }

        document.getElementById('gallery-close').onclick = function() {
            document.getElementById('gallery-modal').classList.remove('show');
        };
        document.getElementById('gallery-modal').onclick = function(e) {
            if (e.target.id === 'gallery-modal') document.getElementById('gallery-modal').classList.remove('show');
        };
        document.getElementById('gallery-prev').onclick = function() {
            const photos = (currentGalleryApt.photos && currentGalleryApt.photos.length) ? currentGalleryApt.photos : [currentGalleryApt.img_src];
            currentPhotoIdx = (currentPhotoIdx - 1 + photos.length) % photos.length;
            showGalleryPhoto(photos, currentPhotoIdx);
        };
        document.getElementById('gallery-next').onclick = function() {
            const photos = (currentGalleryApt.photos && currentGalleryApt.photos.length) ? currentGalleryApt.photos : [currentGalleryApt.img_src];
            currentPhotoIdx = (currentPhotoIdx + 1) % photos.length;
            showGalleryPhoto(photos, currentPhotoIdx);
        };

        function sortApartments(sortType) {
            const sorted = [...apartments];
            if (sortType === 'rating') {
                sorted.sort((a, b) => (getRating(b.url) - getRating(a.url)) || (a.title.localeCompare(b.title)));
            } else if (sortType === 'price') {
                sorted.sort((a, b) => (parseInt((a.price || '').replace(/\\D/g, '')) || 0) - (parseInt((b.price || '').replace(/\\D/g, '')) || 0));
            }
            renderList(sorted);
        }

        function renderList(apartmentsToRender) {
            const listContainer = document.getElementById('list');
            const sortControls = listContainer.querySelector('.sort-controls');
            listContainer.innerHTML = '';
            listContainer.appendChild(sortControls);

            apartmentsToRender.forEach((apt, index) => {
                const rating = getRating(apt.url);
                const photos = (apt.photos && apt.photos.length) ? apt.photos : (apt.img_src ? [apt.img_src] : []);
                const imgSrc = apt.img_src || (photos[0] || '');

                const div = document.createElement('div');
                div.className = 'apartment';
                div.id = 'apartment-' + index;
                div.dataset.url = apt.url;

                let imgHtml = '';
                if (imgSrc) {
                    imgHtml = '<div class="preview-wrap"><img src="' + imgSrc + '" alt="' + (apt.title || '').replace(/"/g, '&quot;') + '"></div>';
                }

                div.innerHTML = imgHtml +
                    '<h3>' + (apt.title || '').replace(/</g, '&lt;') + '</h3>' +
                    '<p class="price">' + (apt.price || '').replace(/</g, '&lt;') + '</p>' +
                    '<p class="address">' + (apt.address || '').replace(/</g, '&lt;') + '</p>' +
                    (apt.metro && apt.metro.length ? '<p class="metro">' + (apt.metro.join(' • ')).replace(/</g, '&lt;') + '</p>' : '') +
                    '<div class="rating-buttons">' +
                    '<button class="rating-btn green ' + (rating === 3 ? 'active' : '') + '" data-rating="3" data-url="' + apt.url + '">👍</button>' +
                    '<button class="rating-btn yellow ' + (rating === 2 ? 'active' : '') + '" data-rating="2" data-url="' + apt.url + '">😐</button>' +
                    '<button class="rating-btn red ' + (rating === 1 ? 'active' : '') + '" data-rating="1" data-url="' + apt.url + '">👎</button>' +
                    '</div>' +
                    '<div class="rating-info" style="color:' + getRatingColor(rating) + '">' + getRatingText(rating) + '</div>';

                const wrap = div.querySelector('.preview-wrap');
                if (wrap) wrap.addEventListener('click', function(e) { e.stopPropagation(); openGallery(apt, 0); });
                div.querySelectorAll('.rating-btn').forEach(btn => {
                    btn.addEventListener('click', function(e) {
                        e.stopPropagation();
                        const r = parseInt(btn.dataset.rating);
                        setRating(apt.url, r);
                        div.querySelector('.rating-info').textContent = getRatingText(r);
                        div.querySelector('.rating-info').style.color = getRatingColor(r);
                        div.querySelectorAll('.rating-btn').forEach(b => b.classList.remove('active'));
                        btn.classList.add('active');
                        if (document.querySelector('.sort-btn.active').dataset.sort === 'rating') sortApartments('rating');
                        updateMarkerIcon(apt, r);
                    });
                });

                div.addEventListener('click', function(e) {
                    if (e.target.closest('.preview-wrap') || e.target.closest('.rating-btn')) return;
                    map.setView([apt.lat, apt.lon], 16);
                    const m = markers.find(mr => mr._apt && mr._apt.url === apt.url);
                    if (m) m.openPopup();
                    document.querySelectorAll('.apartment').forEach(el => el.classList.remove('highlighted'));
                    div.classList.add('highlighted');
                    div.scrollIntoView({ behavior: 'smooth', block: 'center' });
                });

                listContainer.appendChild(div);
            });
        }

        const map = L.map('map').setView([59.9343, 30.3351], 11);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        }).addTo(map);

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

        apartments.forEach((apt, index) => {
            const rating = getRating(apt.url);
            const marker = L.marker([apt.lat, apt.lon], { icon: createIcon(rating) }).addTo(map);
            marker._apt = apt;
            marker.bindPopup('<b>' + (apt.title || '').replace(/</g, '&lt;') + '</b><br>' + (apt.address || '') + '<br><a href="' + apt.url + '" target="_blank">Открыть на Циан</a>');
            marker.on('click', function() {
                document.querySelectorAll('.apartment').forEach(el => el.classList.remove('highlighted'));
                const el = document.querySelector('.apartment[data-url="' + apt.url.replace(/"/g, '\\"') + '"]');
                if (el) { el.classList.add('highlighted'); el.scrollIntoView({ behavior: 'smooth', block: 'center' }); }
            });
            markers.push(marker);
        });

        document.querySelectorAll('.sort-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                document.querySelectorAll('.sort-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                sortApartments(btn.dataset.sort);
            });
        });

        if (apartments.length > 0) {
            const valid = apartments.filter(a => a.lat != null && a.lon != null);
            if (valid.length) {
                const b = L.latLngBounds(valid.map(a => [a.lat, a.lon]));
                map.fitBounds(b, { padding: [30, 30] });
            }
        }

        sortApartments('rating');
    </script>
</body>
</html>'''

    with open(OUT_HTML, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"Создан {OUT_HTML} с {len(apartments)} квартирами.")


if __name__ == '__main__':
    main()
