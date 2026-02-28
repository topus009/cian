/** Рейтинги квартир в localStorage. 3=Отлично, 2=Хорошо, 1=Плохо, 4=Дорога закрыта */
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
