# -*- coding: utf-8 -*-
"""
Геокодирование адресов из data/apartments.json (Nominatim или Yandex).
Запуск: python scripts/geocode_cian.py
Для Yandex задайте переменную окружения YANDEX_GEO_API_KEY.
"""
import json
import os
import re
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
JSON_PATH = os.path.join(ROOT, 'data', 'apartments.json')

try:
    import requests
except ImportError:
    print("Установите: pip install requests")
    exit(1)


def clean_address(addr):
    if not addr:
        return ""
    s = re.sub(r',+', ',', addr).strip().strip(',')
    return re.sub(r'\s+', ' ', s).strip()


def get_coords_nominatim(address: str):
    address = clean_address(address)
    if not address:
        return None, None
    parts = [p.strip() for p in address.split(',') if p.strip()]
    # Варианты запроса: город первым (Санкт-Петербург, улица, дом), потом полный, потом Russia
    queries = []
    if len(parts) >= 2:
        # Санкт-Петербург, улица, номер дома (часто parts[0]=улица, parts[1]=дом)
        street_num = f"{parts[0]}, {parts[1]}"
        if 'Санкт-Петербург' in address:
            queries.append(f"Санкт-Петербург, {street_num}")
        queries.append(street_num)
    if len(parts) >= 3:
        short = f"{parts[0]}, {parts[-2]}, {parts[-1]}"
        queries.append(short)
    queries.append(address)
    for q in queries:
        for query in [q, f"Russia, {q}", f"Saint Petersburg, {q}"]:
            try:
                url = 'https://nominatim.openstreetmap.org/search'
                params = {'q': query, 'format': 'json', 'limit': 1}
                headers = {'User-Agent': 'CianFavoritesMap/1.0 (local project)'}
                r = requests.get(url, params=params, headers=headers, timeout=15)
                r.raise_for_status()
                results = r.json()
                if results:
                    lat, lon = float(results[0]['lat']), float(results[0]['lon'])
                    # Проверка: результат в районе СПб (примерно)
                    if 59.7 < lat < 60.2 and 29.5 < lon < 31.0:
                        return lat, lon
            except Exception:
                continue
    return None, None


def get_coords_yandex(address: str, api_key: str):
    address = clean_address(address)
    if not address or not api_key:
        return None, None
    try:
        url = 'https://geocode-maps.yandex.ru/1.x'
        params = {'apikey': api_key, 'geocode': address, 'format': 'json', 'lang': 'ru_RU'}
        r = requests.get(url, params=params, timeout=12)
        r.raise_for_status()
        data = r.json()
        f = data.get('response', {}).get('GeoObjectCollection', {}).get('featureMember', [])
        if not f:
            return None, None
        pos = f[0].get('GeoObject', {}).get('Point', {}).get('pos', '')
        if pos:
            lon, lat = pos.split()
            return float(lat), float(lon)
    except Exception as e:
        print(f"  Ошибка Yandex: {e}")
    return None, None


# Центр СПб — подставляем при неудачном геокодировании; по нему же определяем «не геокодированные»
DEFAULT_LAT, DEFAULT_LON = 59.9343, 30.3351


def main():
    if not os.path.isfile(JSON_PATH):
        print(f"Сначала запустите parse_cian_favorites.py (нужен {JSON_PATH})")
        return

    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        apartments = json.load(f)

    api_key = os.environ.get('YANDEX_GEO_API_KEY', '').strip()
    use_yandex = bool(api_key)

    # Геокодируем только те записи, у которых координаты не проставлены (дефолтный центр СПб)
    need_geocode = [
        (i, apt) for i, apt in enumerate(apartments)
        if apt.get('lat') == DEFAULT_LAT and apt.get('lon') == DEFAULT_LON
    ]
    if not need_geocode:
        print("Нет квартир с дефолтными координатами (59.9343, 30.3351). Всё уже геокодировано.")
        return

    print(f"Геокодируем {len(need_geocode)} квартир (остальные уже имеют координаты).\n")
    for i, apt in need_geocode:
        addr = apt.get('address') or 'Санкт-Петербург'
        addr = clean_address(addr)
        print(f"[{i+1}/{len(apartments)}] {addr[:70]}...")
        if use_yandex:
            lat, lon = get_coords_yandex(addr, api_key)
        else:
            lat, lon = get_coords_nominatim(addr)
        if lat is not None:
            apt['lat'] = lat
            apt['lon'] = lon
            print(f"  -> {lat}, {lon}")
        else:
            apt['lat'] = DEFAULT_LAT
            apt['lon'] = DEFAULT_LON
            print("  -> не найдено, оставлен центр СПб")
        time.sleep(1.2 if use_yandex else 1.5)

    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(apartments, f, ensure_ascii=False, indent=2)
    print(f"\nСохранено: {JSON_PATH}. Запустите scripts/create_map_cian.py для обновления карты.")


if __name__ == '__main__':
    main()
