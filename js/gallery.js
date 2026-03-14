/** Галерея фото по клику на превью */
let currentGalleryApt = null;
let currentPhotoIdx = 0;

function openGallery(apt, photoIndex) {
    currentGalleryApt = apt;
    const photos = (apt.photos && apt.photos.length) ? apt.photos : (apt.img_src ? [apt.img_src] : []);
    currentPhotoIdx = photoIndex || 0;
    if (photos.length === 0) return;

    document.getElementById('gallery-title').textContent = (typeof getAptId === 'function' && getAptId(apt) ? 'Код ' + getAptId(apt) + ' — ' : '') + (apt.title || '');
    const area = apt.total_area ? apt.total_area + ' м²' : '';
    const price = apt.price || '';
    const year = (typeof getBuildYear === 'function' ? getBuildYear(apt) : (apt.build_year || ''));
    const yearStr = year ? year + ' г.' : '';
    const parts = [area, price, yearStr].filter(Boolean);
    document.getElementById('gallery-subtitle').textContent = parts.join(' · ');
    document.getElementById('gallery-link').href = apt.url || '#';
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

function goGalleryPrev() {
    if (!currentGalleryApt) return;
    const photos = (currentGalleryApt.photos && currentGalleryApt.photos.length) ? currentGalleryApt.photos : [currentGalleryApt.img_src];
    if (photos.length <= 1) return;
    currentPhotoIdx = (currentPhotoIdx - 1 + photos.length) % photos.length;
    showGalleryPhoto(photos, currentPhotoIdx);
}
function goGalleryNext() {
    if (!currentGalleryApt) return;
    const photos = (currentGalleryApt.photos && currentGalleryApt.photos.length) ? currentGalleryApt.photos : [currentGalleryApt.img_src];
    if (photos.length <= 1) return;
    currentPhotoIdx = (currentPhotoIdx + 1) % photos.length;
    showGalleryPhoto(photos, currentPhotoIdx);
}

function initGallery() {
    document.getElementById('gallery-close').onclick = function () {
        document.getElementById('gallery-modal').classList.remove('show');
    };
    document.getElementById('gallery-modal').onclick = function (e) {
        if (e.target.id === 'gallery-modal') document.getElementById('gallery-modal').classList.remove('show');
    };
    document.getElementById('gallery-prev').onclick = goGalleryPrev;
    document.getElementById('gallery-next').onclick = goGalleryNext;

    var wrap = document.querySelector('#gallery-slider .slider-img-wrap');
    if (wrap) {
        wrap.onclick = function (e) {
            if (!currentGalleryApt || e.target.tagName === 'A') return;
            var photos = (currentGalleryApt.photos && currentGalleryApt.photos.length) ? currentGalleryApt.photos : [currentGalleryApt.img_src];
            if (photos.length <= 1) return;
            var rect = wrap.getBoundingClientRect();
            var x = e.clientX - rect.left;
            if (x < rect.width / 2) goGalleryPrev();
            else goGalleryNext();
        };
    }
}
