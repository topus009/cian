/** Рейтинги квартир в localStorage */
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
