// Скрытые ID: BASE с нуля пустой; NEWLY — дополнительные скрытые.
// Циан: id из URL sale/flat/<id>. Авито: id объявления (поле avito_id или число в конце ссылки …_<id>).
// Приоритет «видимые» (остальные — в NEWLY_HIDDEN_IDS): 322494601, 327734707, Авито 7674493053, 7655163507, 7971674555
// Режим «Видимые + последние скрытые»: BASE пуст → показываются все из JSON (логика в map_cian.html).

var APARTMENT_HIDDEN_IDS_BASE = [
];

var NEWLY_HIDDEN_IDS = [
  '313818809',
  '7393360665',
  '7936886804',
  '7955637216',
  '7999935798',
  '8005474986',
];

window.APARTMENT_HIDDEN_IDS_BASE = APARTMENT_HIDDEN_IDS_BASE;
window.APARTMENT_HIDDEN_IDS = APARTMENT_HIDDEN_IDS_BASE.concat(NEWLY_HIDDEN_IDS);
