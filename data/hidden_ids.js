// Скрытые ID: BASE с нуля пустой; NEWLY — дополнительные скрытые.
// Циан: id из URL sale/flat/<id>. Авито: id объявления (поле avito_id или число в конце ссылки …_<id>).
// Видимые (режим «Только видимые»): 325520933, 327963650, …
// Режим «Видимые + последние скрытые»: BASE пуст → показываются все из JSON (логика в map_cian.html).

var APARTMENT_HIDDEN_IDS_BASE = [
];

var NEWLY_HIDDEN_IDS = [

];

window.APARTMENT_HIDDEN_IDS_BASE = APARTMENT_HIDDEN_IDS_BASE;
window.APARTMENT_HIDDEN_IDS = APARTMENT_HIDDEN_IDS_BASE.concat(NEWLY_HIDDEN_IDS);
