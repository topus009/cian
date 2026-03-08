# -*- coding: utf-8 -*-
"""
Обновляет только поле «этаж» (floor) у всех квартир из сохранённых HTML.
Не парсит всю страницу — только читает HTML и вытаскивает этаж из ObjectFactoidsItem или по regex.

Запуск из корня: python scripts/update_floor_only.py
"""
import json
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
JSON_PATH = os.path.join(ROOT, 'data', 'apartments.json')
DATA_DIR = os.path.join(ROOT, 'data')
STATIC_2_DIR = os.path.join(ROOT, 'data', 'static_2')
STATIC_3_DIR = os.path.join(ROOT, 'data', 'static_3')
STATIC_4_DIR = os.path.join(ROOT, 'data', 'static_4')

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Установите: pip install beautifulsoup4")
    sys.exit(1)


def extract_offer_id(url):
    m = re.search(r'sale/flat/(\d+)', url or '')
    return m.group(1) if m else None


def get_html_path(offer_id, img_src):
    """По img_src определить путь к HTML: data/, static_2/, static_3/, static_4/."""
    if not img_src:
        return None
    if 'static_2/' in img_src:
        return os.path.join(STATIC_2_DIR, offer_id + '.html')
    if 'static_3/' in img_src:
        return os.path.join(STATIC_3_DIR, offer_id + '.html')
    if 'static_4/' in img_src:
        return os.path.join(STATIC_4_DIR, offer_id + '.html')
    return os.path.join(DATA_DIR, offer_id + '.html')


def extract_floor_from_html(html):
    """
    Только этаж из HTML. Сначала ObjectFactoidsItem (лейбл «Этаж», значение «4 из 9»),
    иначе regex по тексту страницы.
    """
    soup = BeautifulSoup(html, 'html.parser')
    # ObjectFactoidsItem: первый span — лейбл, второй — значение
    for item in soup.find_all(attrs={'data-name': 'ObjectFactoidsItem'}):
        spans = item.find_all('span', recursive=True)
        if len(spans) < 2:
            continue
        label = (spans[0].get_text(strip=True) or '').strip().lower()
        value = (spans[1].get_text(strip=True) or '').strip()
        if 'этаж' in label and value:
            m = re.search(r'(\d+)\s*[/из]\s*(\d+)', value, re.I)
            if m:
                return f"{m.group(1)}/{m.group(2)}"
    # Fallback: этаж в тексте
    text = soup.get_text(separator=' ', strip=True)[:15000]
    m = re.search(r'этаж[а]?\s*[:\s]*(\d+)\s*[/из]\s*(\d+)', text, re.I) or re.search(r'(\d+)\s*/\s*(\d+)\s*этаж', text, re.I)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    return None


def main():
    if not os.path.isfile(JSON_PATH):
        print(f"Файл не найден: {JSON_PATH}")
        return

    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        apartments = json.load(f)

    updated = 0
    for apt in apartments:
        offer_id = extract_offer_id(apt.get('url', ''))
        if not offer_id:
            continue
        img_src = apt.get('img_src') or ''
        html_path = get_html_path(offer_id, img_src)
        if not html_path or not os.path.isfile(html_path):
            continue
        try:
            with open(html_path, 'r', encoding='utf-8', errors='replace') as f:
                html = f.read()
        except Exception:
            continue
        floor = extract_floor_from_html(html)
        if floor is not None:
            apt['floor'] = floor
            updated += 1
            print(f"  {offer_id}: этаж {floor}")

    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(apartments, f, ensure_ascii=False, indent=2)
    print(f"\nОбновлено этаж у {updated} из {len(apartments)}. Сохранён {JSON_PATH}.")

    try:
        import subprocess
        r = subprocess.run(
            [sys.executable, os.path.join(SCRIPT_DIR, 'create_map_cian.py')],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r.returncode == 0:
            print((r.stdout or '').strip() or "Обновлён data/apartments.js")
        else:
            print("Запустите: python scripts/create_map_cian.py")
    except Exception as e:
        print(f"create_map_cian: {e}. Запустите: python scripts/create_map_cian.py")


if __name__ == '__main__':
    main()
