# -*- coding: utf-8 -*-
"""
Геокодирование адресов из apartments.json (Nominatim или Yandex).
Запускайте после parse_cian_favorites.py. Обновляет lat/lon в apartments.json.
Для Yandex задайте переменную окружения YANDEX_GEO_API_KEY.
"""
import json
import os
import re
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(SCRIPT_DIR, 'apartments.json')

try:
    import requests
except ImportError:
    print("Установите: pip install requests")
    exit(1)


def clean_address(addr):
    """Убираем двойные запятые, лишние пробелы."""
    if not addr:
        return ""
    s = re.sub(r',+', ',', addr).strip().strip(',')
    return re.sub(r'\s+', ' ', s).strip()


def get_coords_nominatim(address: str):
    """Геокодирование через Nominatim (OpenStreetMap). Лучше работает с коротким адресом: город, улица, дом."""
    address = clean_address(address)
    if not address:
        return None, None
    # Сокращаем до "Санкт-Петербург, улица, дом" — Nominatim лучше находит
    parts = [p.strip() for p in address.split(',') if p.strip()]
    if len(parts) >= 3:
        # Берём первый (город), предпоследний или последний (улица/дом)
        short = f"{parts[0]}, {parts[-2]}, {parts[-1]}" if len(parts) >= 3 else address
    else:
        short = address
    for q in [short, address, f"Russia, {short}"]:
        try:
            url = 'https://nominatim.openstreetmap.org/search'
            params = {'q': q, 'format': 'json', 'limit': 1}
            headers = {'User-Agent': 'CianFavoritesMap/1.0 (local project)'}
            r = requests.get(url, params=params, headers=headers, timeout=15)
            r.raise_for_status()
            results = r.json()
            if results:
                return float(results[0]['lat']), float(results[0]['lon'])
        except Exception as e:
            continue
    return None, None


def get_coords_yandex(address: str, api_key: str):
    """Геокодирование через Yandex Geocoder API."""
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


def main():
    if not os.path.isfile(JSON_PATH):
        print(f"Сначала запустите parse_cian_favorites.py (нужен {JSON_PATH})")
        return

    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        apartments = json.load(f)

    api_key = os.environ.get('YANDEX_GEO_API_KEY', '').strip()
    use_yandex = bool(api_key)

    for i, apt in enumerate(apartments):
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
            apt['lat'] = 59.9343
            apt['lon'] = 30.3351
            print("  -> не найдено, подставлен центр СПб")
        time.sleep(1.2 if use_yandex else 1.5)

    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(apartments, f, ensure_ascii=False, indent=2)
    print(f"\nСохранено: {JSON_PATH}. Запустите create_map_cian.py для обновления карты.")


if __name__ == '__main__':
    main()
