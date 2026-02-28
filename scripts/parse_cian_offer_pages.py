# -*- coding: utf-8 -*-
"""
Парсит сохранённые HTML страницы объявлений Циан из data/<ID>.html и data/<ID>_files/.
Извлекает: JSON-LD (описание, цена, название), meta/og (площадь, этаж), локальные фото.
Обновляет data/apartments.json. После запуска: python scripts/create_map_cian.py
"""
import json
import os
import re

from bs4 import BeautifulSoup

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
JSON_PATH = os.path.join(ROOT, 'data', 'apartments.json')
DATA_DIR = os.path.join(ROOT, 'data')

IMAGE_EXT = ('.jpg', '.jpeg', '.png', '.webp')
SKIP_NAMES = ('icon', 'avatar', 'logo', 'svg')


def collect_local_photos(offer_id: str):
    """Собрать пути к фото из data/<ID>_files/ (относительно корня проекта)."""
    folder = os.path.join(DATA_DIR, offer_id + '_files')
    if not os.path.isdir(folder):
        return []
    paths = []
    for name in sorted(os.listdir(folder)):
        base, ext = os.path.splitext(name.lower())
        if ext not in IMAGE_EXT:
            continue
        if any(skip in base.lower() for skip in SKIP_NAMES):
            continue
        rel = 'data/' + offer_id + '_files/' + name.replace('\\', '/')
        paths.append(rel)
    return paths


def extract_ldjson(soup):
    """Извлечь данные из первого script[type=application/ld+json] (Product)."""
    script = soup.find('script', type='application/ld+json')
    if not script or not script.string:
        return {}
    try:
        data = json.loads(script.string.strip())
    except json.JSONDecodeError:
        return {}
    if data.get('@type') != 'Product':
        return {}
    out = {}
    if data.get('description'):
        out['description'] = data['description'].strip()
    if data.get('name'):
        out['title'] = data['name'].strip()
    if data.get('image'):
        imgs = data['image']
        if isinstance(imgs, str):
            imgs = [imgs]
        out['image_urls'] = imgs[:50]
    offers = data.get('offers')
    if isinstance(offers, dict) and 'price' in offers:
        try:
            out['price_value'] = int(offers['price'])
        except (TypeError, ValueError):
            pass
    elif isinstance(offers, list) and offers and isinstance(offers[0], dict) and 'price' in offers[0]:
        try:
            out['price_value'] = int(offers[0]['price'])
        except (TypeError, ValueError):
            pass
    return out


def extract_meta(soup):
    """Площадь, этаж, цена из meta и og:title."""
    out = {}
    # og:title часто: "Продаётся 1-комнатная квартира за 8 250 000 руб., 40.7 м.кв., этаж 17/17"
    og = soup.find('meta', property='og:title')
    if og and og.get('content'):
        t = og['content']
        m_price = re.search(r'за\s+([\d\s]+)\s*руб', t, re.I)
        if m_price:
            out['price_str'] = m_price.group(1).replace(' ', '') + ' ₽'
        m_area = re.search(r'([\d,]+)\s*м\.?кв', t, re.I)
        if m_area:
            out['total_area'] = m_area.group(1).replace(',', '.')
        m_floor = re.search(r'этаж\s+(\d+/\d+)', t, re.I)
        if m_floor:
            out['floor'] = m_floor.group(1)
    desc = soup.find('meta', attrs={'name': 'description'})
    if desc and desc.get('content') and 'total_area' not in out:
        m = re.search(r'площадью\s+([\d,]+)\s*м', desc['content'], re.I)
        if m:
            out['total_area'] = m.group(1).replace(',', '.')
    return out


def parse_html_file(filepath: str, offer_id: str):
    """Парсинг одного HTML: JSON-LD + meta. Локальные фото собираются отдельно через collect_local_photos."""
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        html = f.read()
    soup = BeautifulSoup(html, 'html.parser')
    out = {}
    ld = extract_ldjson(soup)
    out.update(ld)
    meta = extract_meta(soup)
    for k, v in meta.items():
        if k not in out or out[k] is None:
            out[k] = v
    # Цена за м²
    pv = out.get('price_value')
    ta = out.get('total_area')
    if pv and ta:
        try:
            area_num = float(str(ta).replace(',', '.'))
            if area_num > 0:
                out['price_per_sqm'] = round(pv / area_num)
        except (ValueError, TypeError):
            pass
    return out


def main():
    if not os.path.isfile(JSON_PATH):
        print(f"Сначала запустите parse_cian_favorites.py (нужен {JSON_PATH})")
        return

    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        apartments = json.load(f)

    by_id = {}
    for apt in apartments:
        m = re.search(r'sale/flat/(\d+)', apt.get('url', ''))
        if m:
            by_id[m.group(1)] = apt

    # Сканировать data/ — файлы <ID>.html
    if not os.path.isdir(DATA_DIR):
        print(f"Папка не найдена: {DATA_DIR}")
        return

    files = []
    for name in os.listdir(DATA_DIR):
        if name.endswith('.html') and not name.endswith('_files'):
            m = re.match(r'^(\d+)\.html$', name)
            if m:
                offer_id = m.group(1)
                files.append((offer_id, os.path.join(DATA_DIR, name)))

    if not files:
        print(f"В папке {DATA_DIR} нет файлов вида <ID>.html (например 324787026.html).")
        return

    updated = 0
    for offer_id, filepath in files:
        if offer_id not in by_id:
            continue
        apt = by_id[offer_id]

        # Локальные фото из data/<ID>_files/
        local_photos = collect_local_photos(offer_id)
        if local_photos:
            apt['photos'] = local_photos
            apt['img_src'] = local_photos[0]
            updated += 1
            print(f"  {offer_id}: {len(local_photos)} локальных фото")

        # Данные из HTML
        parsed = parse_html_file(filepath, offer_id)
        if parsed.get('description'):
            apt['description'] = parsed['description'][:5000]
        if parsed.get('title'):
            apt['title'] = parsed['title']
        if parsed.get('price_value') is not None:
            apt['price_value'] = parsed['price_value']
            if not apt.get('price') and parsed.get('price_str'):
                apt['price'] = parsed['price_str']
        if parsed.get('total_area') is not None:
            apt['total_area'] = parsed['total_area']
        if parsed.get('floor'):
            apt['floor'] = parsed['floor']
        if parsed.get('price_per_sqm') is not None:
            apt['price_per_sqm'] = parsed['price_per_sqm']

    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(apartments, f, ensure_ascii=False, indent=2)
    print(f"Обновлено квартир: {updated}. Запустите scripts/create_map_cian.py.")


if __name__ == '__main__':
    main()
