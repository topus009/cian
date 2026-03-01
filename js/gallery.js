/** Галерея фото по клику на превью */
let currentGalleryApt = null;
let currentPhotoIdx = 0;

function openGallery(apt, photoIndex) {
    currentGalleryApt = apt;
    const photos = (apt.photos && apt.photos.length) ? apt.photos : (apt.img_src ? [apt.img_src] : []);
    currentPhotoIdx = photoIndex || 0;
    if (photos.length === 0) return;

    document.getElementById('gallery-title').textContent = (typeof getAptId === 'function' && getAptId(apt) ? 'Код ' + getAptId(apt) + ' — ' : '') + (apt.title || '');
    document.getElementById('gallery-description').textContent = apt.description || '';
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

function initGallery() {
    document.getElementById('gallery-close').onclick = function () {
        document.getElementById('gallery-modal').classList.remove('show');
    };
    document.getElementById('gallery-modal').onclick = function (e) {
        if (e.target.id === 'gallery-modal') document.getElementById('gallery-modal').classList.remove('show');
    };
    document.getElementById('gallery-prev').onclick = function () {
        const photos = (currentGalleryApt.photos && currentGalleryApt.photos.length) ? currentGalleryApt.photos : [currentGalleryApt.img_src];
        currentPhotoIdx = (currentPhotoIdx - 1 + photos.length) % photos.length;
        showGalleryPhoto(photos, currentPhotoIdx);
    };
    document.getElementById('gallery-next').onclick = function () {
        const photos = (currentGalleryApt.photos && currentGalleryApt.photos.length) ? currentGalleryApt.photos : [currentGalleryApt.img_src];
        currentPhotoIdx = (currentPhotoIdx + 1) % photos.length;
        showGalleryPhoto(photos, currentPhotoIdx);
    };
}
