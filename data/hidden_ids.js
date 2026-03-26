// Скрытые ID: BASE с нуля пустой; NEWLY — дополнительные скрытые.
// Циан: id из URL sale/flat/<id>. Авито: id объявления (поле avito_id или число в конце ссылки …_<id>).
// Приоритет «видимые» (остальные — в NEWLY_HIDDEN_IDS): 322494601, 327734707, Авито 7674493053, 7971674555
// Режим «Видимые + последние скрытые»: BASE пуст → показываются все из JSON (логика в map_cian.html).

var APARTMENT_HIDDEN_IDS_BASE = [
];

var NEWLY_HIDDEN_IDS = [
];

window.APARTMENT_HIDDEN_IDS_BASE = APARTMENT_HIDDEN_IDS_BASE;
window.APARTMENT_HIDDEN_IDS = APARTMENT_HIDDEN_IDS_BASE.concat(NEWLY_HIDDEN_IDS);
