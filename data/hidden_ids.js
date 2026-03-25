// Скрытые ID: BASE с нуля пустой; NEWLY — дополнительные скрытые.
// Циан: id из URL sale/flat/<id>. Авито: id объявления (поле avito_id или число в конце ссылки …_<id>).
// Приоритет «видимые» (остальные — в NEWLY_HIDDEN_IDS): 322494601, 327734707, 327663356, Авито 7674493053, 7655163507, 7971674555
// Режим «Видимые + последние скрытые»: BASE пуст → показываются все из JSON (логика в map_cian.html).

var APARTMENT_HIDDEN_IDS_BASE = [
];

var NEWLY_HIDDEN_IDS = [
  '313818809',
  '319244695',
  '324889160',
  '324934151',
  '326549828',
  '326748976',
  '327695662',
  '327963650',
  '3689650432',
  '7393360665',
  '7504638383',
  '7936886804',
  '7955637216',
  '7959758116',
  '7999935798',
  '8005474986',
  '8009125697',
];

window.APARTMENT_HIDDEN_IDS_BASE = APARTMENT_HIDDEN_IDS_BASE;
window.APARTMENT_HIDDEN_IDS = APARTMENT_HIDDEN_IDS_BASE.concat(NEWLY_HIDDEN_IDS);
