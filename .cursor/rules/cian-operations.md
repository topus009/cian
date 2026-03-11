# Операции с проектом Циан — инструкции для AI-агента

Проект: интерактивная карта квартир с Циан (СПб) на Leaflet.
Корень: `c:\Users\sj_89\Desktop\cian`

---

## Архитектура данных

```
data/apartments.json          ← главный источник истины (массив квартир)
data/apartments.js            ← автогенерируемый JS: window.APARTMENTS = [...]
data/metro_spb.json / .js     ← станции метро (статичные)
data/<ID>_files/              ← фото квартир (1-я пачка)
data/static_2/<ID>_files/     ← фото квартир (2-я пачка)
data/static_3/<ID>_files/     ← фото квартир (3-я пачка)
data/static_4/<ID>_files/     ← фото квартир (4-я пачка, автоскачивание)
```

**Ключевое правило:** после ЛЮБОГО изменения `apartments.json` нужно перегенерировать JS:
```bash
python scripts/create_map_cian.py
```

---

## 1. УДАЛЕНИЕ КВАРТИР

Пользователь даёт список ID (числа из URL вида `https://spb.cian.ru/sale/flat/<ID>`).

**Важно:** удалять нужно из **apartments.json** и затем перегенерировать **apartments.js**. Если удалять только из apartments.js, то json и js рассинхронизируются — при следующем «полном» удалении или пересборке «вернутся» ранее удалённые квартиры.

### Шаг 1: Удалить из data/apartments.json
```bash
cd "C:\Users\sj_89\Desktop\cian"
python -c "
import json
path = 'data/apartments.json'
with open(path, encoding='utf-8') as f:
    arr = json.load(f)
ids = {'ID1', 'ID2', 'ID3'}  # подставить ID из запроса пользователя
before = len(arr)
arr = [a for a in arr if not any(i in (a.get('url') or '') for i in ids)]
with open(path, 'w', encoding='utf-8') as f:
    json.dump(arr, f, ensure_ascii=False, indent=2)
print(f'Removed {before - len(arr)} apartments')
"
```

### Шаг 2: Перегенерировать apartments.js
```bash
python scripts/create_map_cian.py
```

### Шаг 3 (опционально, «полное» удаление): удалить папки с фото и HTML
```bash
python -c "
import os, shutil
ids = ['ID1','ID2','ID3']
roots = ['data', 'data/static_2', 'data/static_3', 'data/static_4']
for rid in ids:
    for root in roots:
        d = os.path.join(root, rid + '_files')
        if os.path.isdir(d): shutil.rmtree(d)
        f = os.path.join(root, rid + '.html')
        if os.path.isfile(f): os.remove(f)
"
```

---

## 2. ПЕРЕКАЧКА ДАННЫХ / ФОТО ДЛЯ СТАРЫХ КВАРТИР

«Старые» = квартиры с фото НЕ из `data/static_4/` (т.е. из data/, static_2/, static_3/).

### Вариант А: Перекачать фото через requests + Selenium
```bash
cd "c:\Users\sj_89\Desktop\cian"
python scripts/refresh_old_photos_and_remove.py
```
**Внимание:** В этом скрипте захардкожены ID квартир на удаление — проверить/обновить перед запуском!

### Вариант Б: Полный перепарсинг сохранённых HTML
```bash
python scripts/parse_cian_offer_pages.py
python scripts/create_map_cian.py
```
Парсит HTML из `data/`, `data/static_2/`, `data/static_3/`, `data/static_4/` — обновляет описание, цену, площадь, этаж, фото в `apartments.json`, затем генерирует JS.

### Вариант В: Только обновить этаж
```bash
python scripts/update_floor_only.py
```
Автоматически вызывает `create_map_cian.py` в конце.

### Вариант Г: Синхронизировать пути к фото с реальными файлами на диске
```bash
python scripts/sync_cian_photos.py
```

---

## 3. СКАЧАТЬ НОВЫЕ КВАРТИРЫ С ЦИАН (не трогая существующие)

### Шаг 1: Подготовить список URL
Создать/дополнить файл `data/urls_to_fetch.txt` — по одному URL на строку:
```
https://spb.cian.ru/sale/flat/329000001
https://spb.cian.ru/sale/flat/329000002
```

### Шаг 2: Скачать HTML и фото

**Через requests (быстро, может не пройти защиту Циан):**
```bash
python scripts/fetch_cian_offers_by_data_name.py data/urls_to_fetch.txt
```

**Через Selenium/Chrome (надёжно, обходит капчу):**
```bash
python scripts/fetch_cian_offers_selenium.py data/urls_to_fetch.txt
```
- Открывает реальный Chrome
- При капче ждёт ручного решения (до 5 мин)
- Сохраняет HTML в `data/static_4/<ID>.html`, фото в `data/static_4/<ID>_files/`
- Обновляет `apartments.json` после каждой квартиры (прогресс не теряется)

### Шаг 3: Подставить точные координаты
Для КАЖДОЙ новой квартиры нужно найти точные координаты:
1. Найти адрес в 2ГИС
2. Взять lat/lon
3. Обновить в `data/apartments.json`

Или запустить геокодер:
```bash
# Нужен YANDEX_GEO_API_KEY в переменных окружения
python scripts/geocode_cian.py
```

### Шаг 4: Перегенерировать JS для фронтенда
```bash
python scripts/create_map_cian.py
```

### Шаг 5 (если новая папка static_N): Обновить .gitignore
Добавить блок:
```gitignore
!/data/static_N/
/data/static_N/*
!/data/static_N/*_files/
/data/static_N/*_files/*
!/data/static_N/*_files/*.jpg
!/data/static_N/*_files/*.jpeg
```

---

## 4. ДОБАВИТЬ КВАРТИРЫ ИЗ СОХРАНЁННОЙ СТРАНИЦЫ «ИЗБРАННОЕ»

### Если это первая пачка:
```bash
# Сохранить страницу «Избранное» Циан как data/favorite.htm
python scripts/parse_cian_favorites.py
python scripts/geocode_cian.py
python scripts/create_map_cian.py
```

### Если это дополнительная пачка:
```bash
# Сохранить как data/favorite_2.html (или _3, _4...)
# Скрипт merge ожидает файл data/favorite_2.html
python scripts/merge_cian_favorites.py
python scripts/geocode_cian.py
python scripts/create_map_cian.py
```

---

## 5. СПРАВОЧНИК СКРИПТОВ

| Скрипт | Что делает | Аргументы |
|--------|-----------|-----------|
| `parse_cian_favorites.py` | Парсит страницу «Избранное» → apartments.json | нет |
| `merge_cian_favorites.py` | Сливает вторую пачку избранного | нет (читает data/favorite_2.html) |
| `geocode_cian.py` | Геокодирование адресов → lat/lon | нет (env: YANDEX_GEO_API_KEY) |
| `create_map_cian.py` | apartments.json → apartments.js | нет |
| `fetch_cian_offers.py` | Скачивает страницы объявлений (requests) | нет |
| `fetch_cian_offers_by_data_name.py` | Скачивает по списку URL (requests) | [путь к urls.txt] |
| `fetch_cian_offers_selenium.py` | Скачивает через Chrome/Selenium | [путь к urls.txt] |
| `parse_cian_offer_pages.py` | Парсит сохранённые HTML → apartments.json | нет |
| `update_floor_only.py` | Обновляет только поле floor | нет |
| `sync_cian_photos.py` | Синхронизирует photos[] с файлами на диске | нет |
| `refresh_old_photos_and_remove.py` | Перекачивает фото старых квартир | нет |
| `parse_metro_spb.py` | Парсит таблицу метро → metro_spb.json | [файл.html] или --fetch |

---

## 6. ВАЖНЫЕ ПРАВИЛА

1. **НЕ коммитить и НЕ пушить** без явной просьбы пользователя
2. При удалении квартир **всегда** править **apartments.json**, затем запускать `create_map_cian.py`. Не править только apartments.js — иначе json и js рассинхронизируются и при следующей пересборке «вернутся» старые квартиры.
3. После изменения apartments.json — **всегда** запускать `python scripts/create_map_cian.py`
4. `apartments.js` — однострочный JS-файл с `window.APARTMENTS = [...];\n`, автогенерируется из JSON
5. ID квартиры = число из URL: `https://spb.cian.ru/sale/flat/<ID>`
6. Все скрипты запускаются из корня проекта: `cd "C:\Users\sj_89\Desktop\cian"`
7. Зависимости: `beautifulsoup4`, `requests`, `selenium` (опционально)
