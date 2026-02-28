# -*- coding: utf-8 -*-
"""
Читает data/apartments.json, добавляет разброс координат при дубликатах,
записывает data/apartments.js (window.APARTMENTS) для карты.
Запуск из корня: python scripts/create_map_cian.py
"""
import json
import os
import math
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
JSON_PATH = os.path.join(ROOT, 'data', 'apartments.json')
OUT_JS = os.path.join(ROOT, 'data', 'apartments.js')


def jitter_coords(apartments):
    by_key = defaultdict(list)
    for i, apt in enumerate(apartments):
        key = (apt.get('lat'), apt.get('lon'))
        by_key[key].append(i)
    for (lat, lon), indices in by_key.items():
        if lat is None or lon is None or len(indices) <= 1:
            continue
        for k, idx in enumerate(indices):
            angle = 2 * math.pi * k / len(indices)
            offset = 0.002
            apartments[idx]['lat'] = lat + offset * math.cos(angle)
            apartments[idx]['lon'] = lon + offset * math.sin(angle)
    return apartments


def main():
    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        apartments = json.load(f)
    apartments = jitter_coords(apartments)
    js_content = 'window.APARTMENTS = ' + json.dumps(apartments, ensure_ascii=False) + ';\n'
    with open(OUT_JS, 'w', encoding='utf-8') as f:
        f.write(js_content)
    print(f"Записано {OUT_JS} с {len(apartments)} квартирами.")


if __name__ == '__main__':
    main()
