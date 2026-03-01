# -*- coding: utf-8 -*-
"""
Объединяет первый список избранных (15 квартир из data/apartments.json) со вторым
из data/favorite_2.html. Фото для второй пачки берутся из data/static_2/<ID>_files/.
Итог: сначала 15 квартир, затем новые из favorite_2 (без дубликатов по URL).
Запуск: python scripts/merge_cian_favorites.py
Дальше: python scripts/geocode_cian.py (для новых), python scripts/create_map_cian.py
"""
import json
import os
import re

from bs4 import BeautifulSoup

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
JSON_PATH = os.path.join(ROOT, 'data', 'apartments.json')
FAVORITE_2_HTML = os.path.join(ROOT, 'data', 'favorite_2.html')
STATIC_2_DIR = os.path.join(ROOT, 'data', 'static_2')

IMAGE_EXT = ('.jpg', '.jpeg', '.png', '.webp')
SKIP_NAME_PARTS = ('icon.', 'logo.', 'logo-', 'favicon')


def list_photos_in_static2(offer_id: str):
    """Фото из data/static_2/<ID>_files/ (только существующие файлы)."""
    folder = os.path.join(STATIC_2_DIR, offer_id + '_files')
    if not os.path.isdir(folder):
        return []
    paths = []
    for name in sorted(os.listdir(folder)):
        base, ext = os.path.splitext(name)
        if ext.lower() not in IMAGE_EXT:
            continue
        if any(skip in base.lower() for skip in SKIP_NAME_PARTS):
            continue
        rel = 'data/static_2/' + offer_id + '_files/' + name.replace('\\', '/')
        if os.path.isfile(os.path.join(ROOT, rel)):
            paths.append(rel)
    return paths


def parse_favorite_2(html_path: str):
    """Парсит favorite_2.html: ищет ссылки на sale/flat/ID и данные карточки (новая вёрстка Циан)."""
    with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')

    seen_urls = set()
    items = []
    for a in soup.find_all('a', href=re.compile(r'spb\.cian\.ru/sale/flat/\d+')):
        href = a.get('href', '')
        if not href:
            continue
        url = href.strip()
        if not url.startswith('http'):
            url = 'https://' + url.lstrip('/')
        url = url.rstrip('/')
        m = re.search(r'sale/flat/(\d+)', url)
        if not m or url in seen_urls:
            continue
        seen_urls.add(url)
        offer_id = m.group(1)

        card = a
        for _ in range(15):
            if not card:
                break
            card = card.parent
            if not card or card.name != 'div':
                continue
            if 'cad811' in (card.get('class') or []):
                break
        text = card.get_text(separator=' ', strip=True) if card else ''
        price = ''
        pm = re.search(r'(\d[\d\s]*)\s*₽|(\d[\d\s]*)\s*руб', text)
        if pm:
            price = (pm.group(1) or pm.group(2) or '').replace(' ', '') + ' ₽'
        title = 'Квартира'
        if 'комн' in text or 'кв' in text:
            tm = re.search(r'[\d\-]+\s*комн[.\s]*кв[^,]*', text)
            if tm:
                title = tm.group(0).strip()[:80]
        address = 'Санкт-Петербург'
        if 'Санкт-Петербург' in text:
            am = re.search(r'Санкт-Петербург[^.]*', text)
            if am:
                address = re.sub(r'\s+', ' ', am.group(0)).strip()[:200]

        items.append({
            'url': url,
            'title': title,
            'price': price,
            'address': address,
            'metro': [],
            'phone': '',
            'img_src': '',
            'description': '',
            'photos': [],
            'lat': 59.9343,
            'lon': 30.3351,
        })
    return items


def main():
    if not os.path.isfile(JSON_PATH):
        print(f"Нет {JSON_PATH}. Сначала запустите parse_cian_favorites.py (первая пачка).")
        return
    if not os.path.isfile(FAVORITE_2_HTML):
        print(f"Нет {FAVORITE_2_HTML}")
        return

    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        apartments = json.load(f)

    existing_urls = {a['url'] for a in apartments}
    print(f"Текущий список: {len(apartments)} квартир.")

    new_list = parse_favorite_2(FAVORITE_2_HTML)
    print(f"Из favorite_2.html: {len(new_list)} объявлений.")

    added = 0
    for apt in new_list:
        if apt['url'] in existing_urls:
            continue
        offer_id = re.search(r'sale/flat/(\d+)', apt['url'])
        if offer_id:
            offer_id = offer_id.group(1)
            photos = list_photos_in_static2(offer_id)
            if photos:
                apt['photos'] = photos
                apt['img_src'] = photos[0]
            else:
                apt['photos'] = []
        apartments.append(apt)
        existing_urls.add(apt['url'])
        added += 1
        print(f"  + {apt['url']}")

    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(apartments, f, ensure_ascii=False, indent=2)
    print(f"Итого: {len(apartments)} квартир (добавлено {added}).")
    print("Дальше: python scripts/geocode_cian.py — координаты для новых; python scripts/create_map_cian.py — обновить карту.")


if __name__ == '__main__':
    main()
