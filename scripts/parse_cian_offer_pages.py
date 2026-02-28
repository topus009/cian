# -*- coding: utf-8 -*-
"""
Парсит вручную сохранённые HTML страницы объявлений из data/offers/.
Обновляет data/apartments.json: фото и описание. После запуска: python scripts/create_map_cian.py
"""
import json
import os
import re

from bs4 import BeautifulSoup

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
JSON_PATH = os.path.join(ROOT, 'data', 'apartments.json')
OFFERS_DIR = os.path.join(ROOT, 'data', 'offers')


def extract_from_html(html: str, base_path: str):
    """Извлечь фото (локальные пути и URL) и описание из сохранённой страницы."""
    soup = BeautifulSoup(html, 'html.parser')
    photos = []
    description = ''

    for img in soup.find_all('img'):
        src = img.get('src') or img.get('data-src')
        if not src:
            continue
        if 'photo' in src.lower() or 'image' in src.lower() or re.search(r'\.(jpg|jpeg|png|webp)$', src, re.I):
            if src.startswith('http'):
                photos.append(src)
            else:
                if '_files' in src or 'files' in src:
                    parts = src.replace('\\', '/').split('/')
                    if parts[0] in ('.', '..'):
                        path = os.path.normpath(os.path.join(base_path, *parts))
                    else:
                        path = os.path.normpath(os.path.join(base_path, src))
                    rel = os.path.relpath(path, ROOT).replace('\\', '/')
                    photos.append(rel)
                else:
                    photos.append(src)

    for el in soup.find_all(attrs={'data-name': re.compile(r'description|Description')}):
        description += el.get_text(separator='\n', strip=True) + '\n'
    for el in soup.find_all(attrs={'itemprop': 'description'}):
        description += el.get_text(separator='\n', strip=True) + '\n'
    if not description:
        for tag in soup.find_all(['p', 'div'], class_=re.compile(r'description|item-description|text')):
            t = tag.get_text(strip=True)
            if len(t) > 100:
                description += t + '\n'

    seen = set()
    unique = []
    for p in photos:
        key = p.split('?')[0]
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique[:50], description.strip()


def main():
    if not os.path.isfile(JSON_PATH):
        print(f"Сначала запустите parse_cian_favorites.py (нужен {JSON_PATH})")
        return

    os.makedirs(OFFERS_DIR, exist_ok=True)

    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        apartments = json.load(f)

    by_id = {}
    for apt in apartments:
        m = re.search(r'sale/flat/(\d+)', apt.get('url', ''))
        if m:
            by_id[m.group(1)] = apt

    files = []
    for name in os.listdir(OFFERS_DIR):
        if name.endswith('.htm') or name.endswith('.html'):
            m = re.search(r'(\d+)', name)
            if m:
                files.append((m.group(1), os.path.join(OFFERS_DIR, name)))

    if not files:
        print(f"В папке {OFFERS_DIR} нет HTML файлов объявлений.")
        return

    updated = 0
    for offer_id, filepath in files:
        if offer_id not in by_id:
            continue
        apt = by_id[offer_id]
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            html = f.read()
        base = os.path.dirname(filepath)
        photos, desc = extract_from_html(html, base)
        if photos:
            apt['photos'] = photos
            if not apt.get('img_src'):
                apt['img_src'] = photos[0]
            updated += 1
            print(f"  {offer_id}: {len(photos)} фото")
        if desc:
            apt['description'] = desc[:3000]
    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(apartments, f, ensure_ascii=False, indent=2)
    print(f"Обновлено квартир: {updated}. Запустите scripts/create_map_cian.py.")


if __name__ == '__main__':
    main()
