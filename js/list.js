/** Список квартир в сайдбаре, сортировка, рейтинги */
function getBuildYear(apt) {
    if (apt.build_year) return String(apt.build_year);
    const desc = (apt.description || '') + ' ' + (apt.title || '');
    const m = desc.match(/(\d{4})\s*года?\s*постройки|построен[а]?\s*в\s*(\d{4})|(\d{4})\s*год[а]?\s*постройки|дом[а]?\s*(\d{4})|(\d{4})\s*г\.?\s*постройки/i);
    if (m) return (m[1] || m[2] || m[3] || m[4] || m[5] || '').trim();
    const year = desc.match(/\b(19\d{2}|20\d{2})\s*год/i);
    return year ? year[1] : '';
}

function sortApartments(sortType) {
    const apartments = window.APARTMENTS || [];
    const sorted = [...apartments];
    if (sortType === 'rating') {
        sorted.sort((a, b) => {
            const orderA = getRatingSortOrder(getRating(a.url));
            const orderB = getRatingSortOrder(getRating(b.url));
            return orderB - orderA || (a.title.localeCompare(b.title));
        });
    } else if (sortType === 'price') {
        sorted.sort((a, b) => (parseInt((a.price || '').replace(/\D/g, '')) || 0) - (parseInt((b.price || '').replace(/\D/g, '')) || 0));
    }
    renderList(sorted);
}

function renderList(apartmentsToRender) {
    const listContainer = document.getElementById('list');
    const sortControls = listContainer.querySelector('.sort-controls');
    listContainer.innerHTML = '';
    listContainer.appendChild(sortControls);

    const total = apartmentsToRender.length;
    apartmentsToRender.forEach((apt, index) => {
        const rating = getRating(apt.url);
        const photos = (apt.photos && apt.photos.length) ? apt.photos : (apt.img_src ? [apt.img_src] : []);
        const imgSrc = apt.img_src || (photos[0] || '');

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
        div.innerHTML = '<span class="card-index">' + num + ' из ' + total + '</span>' +
            imgHtml +
            '<h3>' + (apt.title || '').replace(/</g, '&lt;') + '</h3>' +
            '<p class="price">' + (apt.price || '').replace(/</g, '&lt;') + '</p>' +
            (buildYear ? '<p class="build-year">Год постройки: ' + buildYear + '</p>' : '') +
            '<p class="address">' + (apt.address || '').replace(/</g, '&lt;') + '</p>' +
            (apt.metro && apt.metro.length ? '<p class="metro">' + (apt.metro.join(' • ')).replace(/</g, '&lt;') + '</p>' : '') +
            '<div class="rating-buttons">' +
            '<button class="rating-btn green ' + (rating === 3 ? 'active' : '') + '" data-rating="3" data-url="' + apt.url + '">👍</button>' +
            '<button class="rating-btn yellow ' + (rating === 2 ? 'active' : '') + '" data-rating="2" data-url="' + apt.url + '">😐</button>' +
            '<button class="rating-btn red ' + (rating === 1 ? 'active' : '') + '" data-rating="1" data-url="' + apt.url + '">👎</button>' +
            '<button class="rating-btn closed ' + (rating === 4 ? 'active' : '') + '" data-rating="4" data-url="' + apt.url + '" title="Дорога закрыта">🚫</button>' +
            '</div>' +
            '<div class="card-footer">' +
            '<span class="rating-info" style="color:' + getRatingColor(rating) + '">' + getRatingText(rating) + '</span>' +
            '<a class="btn-cian-card" href="' + (apt.url || '#').replace(/"/g, '&quot;') + '" target="_blank" rel="noopener">Циан</a>' +
            '</div>';

        const wrap = div.querySelector('.preview-wrap');
        if (wrap) wrap.addEventListener('click', function (e) { e.stopPropagation(); openGallery(apt, 0); });
        div.querySelectorAll('.rating-btn').forEach(btn => {
            btn.addEventListener('click', function (e) {
                e.stopPropagation();
                const r = parseInt(btn.dataset.rating);
                setRating(apt.url, r);
                div.querySelector('.rating-info').textContent = getRatingText(r);
                div.querySelector('.rating-info').style.color = getRatingColor(r);
                div.querySelectorAll('.rating-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                div.classList.toggle('rating-closed', isRatingClosed(r));
                if (document.querySelector('.sort-btn.active').dataset.sort === 'rating') sortApartments('rating');
                updateMarkerIcon(apt, r);
            });
        });

        div.addEventListener('click', function (e) {
            if (e.target.closest('.preview-wrap') || e.target.closest('.rating-btn') || e.target.closest('.btn-cian-card')) return;
            if (rating === 4) {
                e.preventDefault();
                setRating(apt.url, 0);
                div.querySelector('.rating-info').textContent = getRatingText(0);
                div.querySelector('.rating-info').style.color = getRatingColor(0);
                div.querySelectorAll('.rating-btn').forEach(b => { b.classList.remove('active'); });
                div.classList.remove('rating-closed');
                updateMarkerIcon(apt, 0);
                if (document.querySelector('.sort-btn.active').dataset.sort === 'rating') sortApartments('rating');
                return;
            }
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

function initList() {
    const apartments = window.APARTMENTS || [];
    document.querySelectorAll('.sort-btn').forEach(btn => {
        btn.addEventListener('click', function () {
            document.querySelectorAll('.sort-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            sortApartments(btn.dataset.sort);
        });
    });
    sortApartments('rating');
}
