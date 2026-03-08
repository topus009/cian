# -*- coding: utf-8 -*-
"""
Геокодирование адресов из data/apartments.json через Yandex Geocoder API v1.
Обновляет координаты (lat, lon) для всех квартир по полю address.

Формат запроса (обязательные: apikey, geocode, lang; format=json).
Ответ: response.GeoObjectCollection.featureMember[0].GeoObject.Point.pos
       в формате «долгота широта» (longitude latitude).

Использование:
  export YANDEX_GEO_API_KEY=ваш_ключ   # Linux/Mac/Git Bash
  set YANDEX_GEO_API_KEY=ваш_ключ     # Windows cmd
  python scripts/geocode_cian.py

В конце вызывается create_map_cian.py для обновления data/apartments.js.
"""
import json
import os
import re
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
JSON_PATH = os.path.join(ROOT, 'data', 'apartments.json')

try:
    import requests
except ImportError:
    print("Установите: pip install requests")
    sys.exit(1)

# Базовый URL Yandex Geocoder API v1 (как в документации)
YANDEX_GEO_V1_URL = "https://geocode-maps.yandex.ru/v1/"

# Заголовки: при ограничении ключа по Referer в кабинете Яндекса укажите свой домен или отключите ограничения
GEO_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://yandex.ru/",
}


def clean_address(addr):
    if not addr:
        return ""
    s = re.sub(r',+', ',', addr).strip().strip(',')
    return re.sub(r'\s+', ' ', s).strip()


def get_coords_yandex_v1(address: str, api_key: str):
    """Геокодирование через Yandex Geocoder API v1. Возвращает (lat, lon) или (None, None)."""
    address = clean_address(address)
    if not address or not api_key:
        return None, None
    try:
        params = {
            "apikey": api_key,
            "geocode": address,
            "format": "json",
            "lang": "ru_RU",
        }
        r = requests.get(YANDEX_GEO_V1_URL, params=params, headers=GEO_HEADERS, timeout=12)
        r.raise_for_status()
        data = r.json()
        members = (
            data.get("response", {})
            .get("GeoObjectCollection", {})
            .get("featureMember", [])
        )
        if not members:
            return None, None
        pos = (
            members[0]
            .get("GeoObject", {})
            .get("Point", {})
            .get("pos", "")
        )
        if not pos:
            return None, None
        # Документация: "longitude latitude"
        parts = pos.split()
        if len(parts) != 2:
            return None, None
        lon, lat = float(parts[0]), float(parts[1])
        return lat, lon
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 403:
            print("  403 Forbidden (документация: «В запросе указан неверный apikey»).")
            print("  Проверьте: ключ из Кабинета Разработчика для Геокодера; активация до 15 мин после создания.")
        else:
            print(f"  Ошибка Yandex: {e}")
    except Exception as e:
        print(f"  Ошибка Yandex: {e}")
    return None, None


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


def get_coords_yandex_1x(address: str, api_key: str):
    """Старый API 1.x (на случай если ключ только под него)."""
    address = clean_address(address)
    if not address or not api_key:
        return None, None
    try:
        url = "https://geocode-maps.yandex.ru/1.x"
        params = {"apikey": api_key, "geocode": address, "format": "json", "lang": "ru_RU"}
        r = requests.get(url, params=params, headers=GEO_HEADERS, timeout=12)
        r.raise_for_status()
        data = r.json()
        f = data.get("response", {}).get("GeoObjectCollection", {}).get("featureMember", [])
        if not f:
            return None, None
        pos = f[0].get("GeoObject", {}).get("Point", {}).get("pos", "")
        if pos:
            lon, lat = pos.split()
            return float(lat), float(lon)
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 403:
            pass  # уже выведено в v1
        else:
            print(f"  Ошибка Yandex 1.x: {e}")
    except Exception as e:
        print(f"  Ошибка Yandex 1.x: {e}")
    return None, None


# Центр СПб — подставляем при неудачном геокодировании
DEFAULT_LAT, DEFAULT_LON = 59.9343, 30.3351


def main():
    if not os.path.isfile(JSON_PATH):
        print(f"Файл не найден: {JSON_PATH}")
        return

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        apartments = json.load(f)

    api_key = os.environ.get("YANDEX_GEO_API_KEY", "").strip()
    if not api_key:
        print("Переменная YANDEX_GEO_API_KEY не задана.")
        print("Задайте ключ и перезапустите: export YANDEX_GEO_API_KEY=ваш_ключ")
        sys.exit(1)

    # Геокодируем все квартиры по полю address (правим координаты для всех)
    n = len(apartments)
    print(f"Геокодируем {n} квартир через Yandex Geocoder API v1.\n")

    for i, apt in enumerate(apartments):
        addr = apt.get("address") or "Санкт-Петербург"
        addr = clean_address(addr)
        if not addr:
            addr = "Санкт-Петербург"
        print(f"[{i+1}/{n}] {addr[:75]}...")
        lat, lon = get_coords_yandex_v1(addr, api_key)
        if lat is None and lon is None:
            lat, lon = get_coords_yandex_1x(addr, api_key)
        if lat is None and lon is None:
            time.sleep(1.0)  # Nominatim: не более 1 запроса в секунду
            lat, lon = get_coords_nominatim(addr)
            if lat is not None:
                print("  (Nominatim)")
        if lat is not None and lon is not None:
            apt["lat"] = lat
            apt["lon"] = lon
            print(f"  -> {lat}, {lon}")
        else:
            apt["lat"] = DEFAULT_LAT
            apt["lon"] = DEFAULT_LON
            print("  -> не найдено, оставлен центр СПб")
        time.sleep(0.5 if (lat is not None) else 0.35)

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(apartments, f, ensure_ascii=False, indent=2)
    print(f"\nСохранено: {JSON_PATH}")

    # Обновить apartments.js для карты
    try:
        import subprocess
        r = subprocess.run(
            [sys.executable, os.path.join(SCRIPT_DIR, "create_map_cian.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r.returncode == 0:
            print(r.stdout.strip() if r.stdout else "Обновлён data/apartments.js")
        else:
            print("Запустите: python scripts/create_map_cian.py")
    except Exception as e:
        print(f"Обновление карты: {e}. Запустите: python scripts/create_map_cian.py")


if __name__ == '__main__':
    main()
