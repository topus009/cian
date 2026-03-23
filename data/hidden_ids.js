// Скрытые ID: BASE с нуля пустой; NEWLY — все квартиры из данных, кроме видимых 6.
// Видимые (режим «Только видимые»): 325520933, 327963650, 326748976, 317668714, 322494601, 327734707
// Режим «Видимые + последние скрытые»: BASE пуст → показываются все из JSON (логика в map_cian.html).

var APARTMENT_HIDDEN_IDS_BASE = [
];

var NEWLY_HIDDEN_IDS = [

];

window.APARTMENT_HIDDEN_IDS_BASE = APARTMENT_HIDDEN_IDS_BASE;
window.APARTMENT_HIDDEN_IDS = APARTMENT_HIDDEN_IDS_BASE.concat(NEWLY_HIDDEN_IDS);
