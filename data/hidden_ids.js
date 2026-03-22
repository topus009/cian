// Скрытые ID: BASE с нуля пустой; NEWLY — все квартиры из данных, кроме видимых 6.
// Видимые (режим «Только видимые»): 325520933, 327963650, 326748976, 317668714, 322494601, 327734707
// Режим «Видимые + последние скрытые»: BASE пуст → показываются все из JSON (логика в map_cian.html).

var APARTMENT_HIDDEN_IDS_BASE = [
];

var NEWLY_HIDDEN_IDS = [
    '319244695','326300002','327401764','327695662','324934151',
    '305124124','326386990','327528262','326549828','327956434',
    '327351946','327845364','313818809','324889160',
];

window.APARTMENT_HIDDEN_IDS_BASE = APARTMENT_HIDDEN_IDS_BASE;
window.APARTMENT_HIDDEN_IDS = APARTMENT_HIDDEN_IDS_BASE.concat(NEWLY_HIDDEN_IDS);
