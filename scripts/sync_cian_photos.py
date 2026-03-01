# -*- coding: utf-8 -*-
"""
Синхронизирует список фото в data/apartments.json с реальными файлами в data/<ID>_files/.
Проходит по всем папкам статики, оставляет в каждой квартире только пути к существующим картинкам —
битые ссылки (удалённые дубликаты, реклама и т.п.) убираются.
Запуск: python scripts/sync_cian_photos.py
После этого: python scripts/create_map_cian.py
"""
import json
import os
import re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
JSON_PATH = os.path.join(ROOT, 'data', 'apartments.json')
DATA_DIR = os.path.join(ROOT, 'data')

IMAGE_EXT = ('.jpg', '.jpeg', '.png', '.webp')
SKIP_NAME_PARTS = ('icon.', 'logo.', 'logo-', 'favicon')


def list_existing_photos(offer_id: str):
    """Список путей к фото, которые реально есть в data/<ID>_files/ (относительно корня)."""
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
        full = os.path.join(ROOT, rel)
        if os.path.isfile(full):
            paths.append(rel)
    return paths


def main():
    if not os.path.isfile(JSON_PATH):
        print(f"Нет файла {JSON_PATH}")
        return

    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        apartments = json.load(f)

    updated = 0
    for apt in apartments:
        m = re.search(r'sale/flat/(\d+)', apt.get('url', ''))
        if not m:
            continue
        offer_id = m.group(1)
        existing = list_existing_photos(offer_id)
        old_photos = apt.get('photos') or []
        if existing != old_photos:
            apt['photos'] = existing
            apt['img_src'] = existing[0] if existing else (apt.get('img_src') or '')
            updated += 1
            print(f"  {offer_id}: было {len(old_photos)} фото, осталось {len(existing)}")

    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(apartments, f, ensure_ascii=False, indent=2)
    print(f"Обновлено записей: {updated}. Запустите: python scripts/create_map_cian.py")


if __name__ == '__main__':
    main()
