# -*- coding: utf-8 -*-
"""
Парсит сохранённые HTML страницы объявлений Циан из data/<ID>.html и data/<ID>_files/.
Сканирует папку data/ по маске <ID>.html (ID — число из URL объявления).
Для каждой квартиры: извлекает из HTML JSON-LD (описание, цена, название), meta/og (площадь, этаж),
собирает ВСЕ фото из папки data/<ID>_files/, обновляет запись в data/apartments.json.
После запуска: python scripts/create_map_cian.py
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
# Исключаем только явные иконки интерфейса (не фото квартир)
SKIP_NAME_PARTS = ('icon.', 'logo.', 'logo-', 'favicon')


def collect_local_photos(offer_id: str):
    """Собрать ВСЕ пути к фото из data/<ID>_files/ (относительно корня проекта)."""
    folder = os.path.join(DATA_DIR, offer_id + '_files')
    if not os.path.isdir(folder):
        return []
    paths = []
    for name in sorted(os.listdir(folder)):
        base, ext = os.path.splitext(name)
        if ext.lower() not in IMAGE_EXT:
            continue
        base_lower = base.lower()
        if any(skip in base_lower for skip in SKIP_NAME_PARTS):
            continue
        rel = 'data/' + offer_id + '_files/' + name.replace('\\', '/')
        paths.append(rel)
    return paths


def extract_ldjson(soup):
    """Извлечь данные из script[type=application/ld+json]. Поддержка @graph."""
    for script in soup.find_all('script', type='application/ld+json'):
        if not script.string:
            continue
        try:
            data = json.loads(script.string.strip())
        except json.JSONDecodeError:
            continue
        # Может быть один объект Product или массив в @graph
        items = []
        if data.get('@type') == 'Product':
            items.append(data)
        if data.get('@graph'):
            for item in data['@graph']:
                if isinstance(item, dict) and item.get('@type') == 'Product':
                    items.append(item)
        if not items:
            continue
        obj = items[0]
        out = {}
        desc = obj.get('description')
        if desc:
            if isinstance(desc, list):
                out['description'] = '\n'.join(str(x) for x in desc).strip()
            else:
                out['description'] = str(desc).strip()
        if obj.get('name'):
            out['title'] = str(obj['name']).strip()
        if obj.get('image'):
            imgs = obj['image']
            if isinstance(imgs, str):
                imgs = [imgs]
            out['image_urls'] = imgs[:50]
        offers = obj.get('offers')
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
        if out:
            return out
    return {}


def extract_meta(soup):
    """Площадь, этаж, цена из meta и og:title."""
    out = {}
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


def parse_html_file(filepath: str):
    """Парсинг одного HTML: JSON-LD + meta."""
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

    if not os.path.isdir(DATA_DIR):
        print(f"Папка не найдена: {DATA_DIR}")
        return

    # Только файлы вида 324787026.html в корне data/ (не во вложенных папках)
    files = []
    for name in os.listdir(DATA_DIR):
        m = re.match(r'^(\d+)\.html$', name)
        if m:
            offer_id = m.group(1)
            path = os.path.join(DATA_DIR, name)
            if os.path.isfile(path):
                files.append((offer_id, path))

    if not files:
        print(f"В папке {DATA_DIR} нет файлов вида <ID>.html (например 324787026.html).")
        return

    print(f"Найдено HTML в data/: {len(files)}. Квартир в JSON: {len(by_id)}.")

    updated_any = 0
    for offer_id, filepath in files:
        if offer_id not in by_id:
            print(f"  Пропуск {offer_id}: нет в apartments.json")
            continue
        apt = by_id[offer_id]
        changed = False

        # 1) Локальные фото из data/<ID>_files/
        local_photos = collect_local_photos(offer_id)
        if local_photos:
            apt['photos'] = local_photos
            apt['img_src'] = local_photos[0]
            changed = True
            print(f"  {offer_id}: {len(local_photos)} фото из {offer_id}_files/")

        # 2) Данные из HTML (описание, цена, площадь, этаж)
        parsed = parse_html_file(filepath)
        if parsed.get('description'):
            apt['description'] = parsed['description'][:5000]
            changed = True
        if parsed.get('title'):
            apt['title'] = parsed['title']
            changed = True
        if parsed.get('price_value') is not None:
            apt['price_value'] = parsed['price_value']
            if parsed.get('price_str'):
                apt['price'] = parsed['price_str']
            changed = True
        if parsed.get('total_area') is not None:
            apt['total_area'] = parsed['total_area']
            changed = True
        if parsed.get('floor'):
            apt['floor'] = parsed['floor']
            changed = True
        if parsed.get('price_per_sqm') is not None:
            apt['price_per_sqm'] = parsed['price_per_sqm']
            changed = True

        if changed:
            updated_any += 1

    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(apartments, f, ensure_ascii=False, indent=2)
    print(f"Обновлено квартир: {updated_any}. Запустите: python scripts/create_map_cian.py")


if __name__ == '__main__':
    main()
