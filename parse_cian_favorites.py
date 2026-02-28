# -*- coding: utf-8 -*-
"""
Парсинг избранных объявлений Циан из сохранённой страницы data/favorite.htm.
Извлекает: ссылка, превью, заголовок, полная цена, полный адрес (строка как на сайте),
метро (название + время до каждого), телефон. Геокодирует полный адрес через
Nominatim или Yandex Geocoder (если задан YANDEX_GEO_API_KEY) для координат на карте.
Результат: apartments.json.
"""
import json
import re
import os
import time

from bs4 import BeautifulSoup

try:
    import requests
except ImportError:
    requests = None

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
FAVORITE_HTML = os.path.join(DATA_DIR, 'favorite.htm')
OUT_JSON = os.path.join(os.path.dirname(__file__), 'apartments.json')


def get_coords_nominatim(address: str):
    """Геокодирование через Nominatim (OpenStreetMap)."""
    if not requests:
        return None, None
    try:
        # Для российских адресов часто помогает добавление "Россия"
        q = address if address.strip().startswith(('Россия', 'Russia')) else f"Россия, {address}"
        url = 'https://nominatim.openstreetmap.org/search'
        params = {'q': q, 'format': 'json', 'limit': 1}
        headers = {'User-Agent': 'CianFavoritesMap/1.0 (local project)'}
        r = requests.get(url, params=params, headers=headers, timeout=12)
        r.raise_for_status()
        results = r.json()
        if results:
            return float(results[0]['lat']), float(results[0]['lon'])
    except Exception as e:
        print(f"  Nominatim: {e}")
    return None, None


def get_coords_yandex(address: str, api_key: str):
    """Геокодирование через Yandex Geocoder API (нужен API ключ)."""
    if not requests or not api_key:
        return None, None
    try:
        url = 'https://geocode-maps.yandex.ru/1.x'
        params = {'apikey': api_key, 'geocode': address, 'format': 'json', 'lang': 'ru_RU'}
        r = requests.get(url, params=params, timeout=10)
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
        print(f"  Yandex: {e}")
    return None, None


def get_coords(address: str):
    """Пробуем Yandex (если ключ задан), иначе Nominatim."""
    api_key = os.environ.get('YANDEX_GEO_API_KEY', '').strip()
    if api_key:
        lat, lon = get_coords_yandex(address, api_key)
        if lat is not None:
            return lat, lon
    return get_coords_nominatim(address)


def parse_favorite_html(html_path: str):
    """Парсит favorite.htm и возвращает список объявлений с полным адресом, метро, телефоном."""
    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')

    items = []
    for card in soup.find_all('div', attrs={'data-name': 'FavoriteEntity'}):
        a_link = card.find('a', href=re.compile(r'spb\.cian\.ru/sale/flat/\d+'))
        if not a_link or not a_link.get('href'):
            continue
        url = a_link['href'].rstrip('/')
        if not url.startswith('http'):
            url = 'https://' + url.lstrip('/')

        # Заголовок
        title_node = card.find('div', attrs={'data-name': 'MainTitle'})
        if title_node:
            a = title_node.find('a')
            title = (a.get_text(strip=True) if a else title_node.get_text(strip=True)).replace('\xa0', ' ')
        else:
            title = 'Квартира'

        # Цена (полная, как на сайте)
        price = ''
        price_block = card.find('div', attrs={'data-name': 'price_info'})
        if price_block:
            span = price_block.find('span', class_=re.compile(r'bold'))
            if span:
                price = span.get_text(strip=True).replace('\xa0', ' ')

        # Превью
        img = card.find('img', alt=re.compile(r'фото|объявлен', re.I))
        if not img:
            img = card.find('div', attrs={'data-name': 'MainImage'})
            img = img.find('img') if img else None
        img_src = ''
        if img and img.get('src'):
            img_src = img['src']
            if img_src.startswith('./'):
                img_src = 'data/' + img_src[2:]
            elif img_src.startswith('favorite_files/'):
                img_src = 'data/' + img_src

        # Полный адрес и метро из geo_info (блок с классом *_29d89--geo_info, без data-name)
        geo = card.find('div', class_=re.compile(r'geo_info'))
        if not geo:
            geo = card.find('div', attrs={'data-name': 'geo_info'})
        address_full = 'Санкт-Петербург'
        metro_lines = []
        if geo:
            # Метро: каждый div[data-name="Underground"] — название + время
            for ug in geo.find_all('div', attrs={'data-name': 'Underground'}):
                t = ug.get_text(separator=' ', strip=True)
                t = re.sub(r'\s+', ' ', t)
                if t:
                    metro_lines.append(t)
            # Адрес: в geo есть один div без data-name с адресными спанами — берём его текст
            for child in geo.find_all('div', recursive=False):
                if child.get('data-name') == 'Underground':
                    continue
                addr_text = child.get_text(separator=', ', strip=True)
                addr_text = re.sub(r',\s*,', ',', re.sub(r'\s+', ' ', addr_text)).strip()
                if addr_text and len(addr_text) > 5:
                    address_full = re.sub(r',+', ',', addr_text).strip().strip(',')
                    break
            if address_full == 'Санкт-Петербург':
                # запасной вариант: убрать Underground и взять весь текст из geo
                clone = BeautifulSoup(str(geo), 'html.parser')
                for div in clone.find_all('div', attrs={'data-name': 'Underground'}):
                    div.decompose()
                addr_text = clone.get_text(separator=', ', strip=True)
                address_full = re.sub(r',+', ',', re.sub(r'\s+', ' ', addr_text).strip()).strip(',').strip() or address_full

        # Телефон (кнопка с номером в блоке controls)
        phone = ''
        controls = card.find('div', class_=re.compile(r'controls'))
        if controls:
            btn = controls.find('button', string=re.compile(r'\+7\s*\d'))
            if btn:
                phone = btn.get_text(strip=True)
            if not phone:
                for btn in controls.find_all('button'):
                    t = btn.get_text(strip=True)
                    if re.match(r'\+7[\s\d\-]+', t):
                        phone = t
                        break

        # Краткое описание
        desc_node = card.find('span', attrs={'data-name': 'Description'})
        description = desc_node.get_text(strip=True)[:500] if desc_node else ''

        items.append({
            'url': url,
            'title': title,
            'price': price,
            'address': address_full,
            'metro': metro_lines,
            'phone': phone,
            'img_src': img_src,
            'description': description,
            'photos': [img_src] if img_src else [],
        })

    return items


def main():
    if not os.path.isfile(FAVORITE_HTML):
        print(f"Файл не найден: {FAVORITE_HTML}")
        return

    print("Парсинг", FAVORITE_HTML)
    apartments = parse_favorite_html(FAVORITE_HTML)
    print(f"Найдено объявлений: {len(apartments)}")

    # Координаты не заполняем здесь — запустите geocode_cian.py после парсинга
    for apt in apartments:
        apt.setdefault('lat', 59.9343)
        apt.setdefault('lon', 30.3351)

    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(apartments, f, ensure_ascii=False, indent=2)

    print(f"Сохранено: {OUT_JSON}")
    print("Дальше: python geocode_cian.py — получить координаты; python create_map_cian.py — обновить карту.")


if __name__ == '__main__':
    main()
