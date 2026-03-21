// Список ID квартир, которые скрыты из карты и списка (но остаются в данных).
// Добавляйте или удаляйте ID — после обновления страницы квартиры исчезнут/появятся.
// ID берётся из ссылки: https://spb.cian.ru/sale/flat/326123456 → 326123456

// Ранее скрытые ID
var APARTMENT_HIDDEN_IDS_BASE = [
    '324783945','318304338',
];

// Дополнительно скрытые ID (после отбора)
var NEWLY_HIDDEN_IDS = [
    '305124124','313083529','319244695','324934151','326300002',
    '326386990','326387899','327401764','327528262','327695662',
];

window.APARTMENT_HIDDEN_IDS_BASE = APARTMENT_HIDDEN_IDS_BASE;
window.APARTMENT_HIDDEN_IDS = APARTMENT_HIDDEN_IDS_BASE.concat(NEWLY_HIDDEN_IDS);
