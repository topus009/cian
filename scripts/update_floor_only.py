# -*- coding: utf-8 -*-
"""
Обновляет поле «этаж» (floor) только у квартир, где оно пустое, из сохранённого HTML.

Источники: meta og:title («этаж 4/18»), ObjectFactoidsItem / OfferSummaryInfoItem (span/p),
regex по HTML и тексту страницы. Поиск файла: static_4/3/2 и data/<id>.html.

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


def resolve_html_path(offer_id, img_src):
    """Путь к сохранённому HTML: сначала по подсказке из img_src, затем static_4…data/."""
    fname = offer_id + '.html'
    candidates = []
    src = img_src or ''
    if 'static_2/' in src:
        candidates.append(os.path.join(STATIC_2_DIR, fname))
    if 'static_3/' in src:
        candidates.append(os.path.join(STATIC_3_DIR, fname))
    if 'static_4/' in src:
        candidates.append(os.path.join(STATIC_4_DIR, fname))
    if 'static_2/' not in src and 'static_3/' not in src and 'static_4/' not in src:
        candidates.append(os.path.join(DATA_DIR, fname))
    for d in (STATIC_4_DIR, STATIC_3_DIR, STATIC_2_DIR, DATA_DIR):
        p = os.path.join(d, fname)
        if p not in candidates:
            candidates.append(p)
    seen = set()
    for p in candidates:
        if p in seen:
            continue
        seen.add(p)
        if os.path.isfile(p):
            return p
    return None


def _floor_from_label_value(label, value):
    label = (label or '').strip().lower()
    value = (value or '').strip()
    if 'этаж' not in label or not value:
        return None
    m = re.search(r'(\d+)\s*[/из]\s*(\d+)', value, re.I)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    return None


def extract_floor_from_html(html):
    """
    Этаж из HTML: meta og:title («этаж 4/18»), ObjectFactoidsItem (span/p),
    OfferSummaryInfoItem, regex по сырому HTML и тексту страницы.
    """
    # 1) og:title — актуальная вёрстка Циан без ObjectFactoidsItem в DOM
    m_og = re.search(
        r'<meta\s[^>]*property\s*=\s*["\']og:title["\'][^>]*content\s*=\s*["\']([^"\']*)["\']',
        html,
        re.I,
    )
    if not m_og:
        m_og = re.search(
            r'<meta\s[^>]*content\s*=\s*["\']([^"\']*)["\'][^>]*property\s*=\s*["\']og:title["\']',
            html,
            re.I,
        )
    if m_og:
        m = re.search(r'этаж\s*(\d+)\s*/\s*(\d+)', m_og.group(1), re.I)
        if m:
            return f"{m.group(1)}/{m.group(2)}"

    soup = BeautifulSoup(html, 'html.parser')
    og = soup.find('meta', attrs={'property': 'og:title'})
    if og and og.get('content'):
        m = re.search(r'этаж\s*(\d+)\s*/\s*(\d+)', og['content'], re.I)
        if m:
            return f"{m.group(1)}/{m.group(2)}"

    # 2) ObjectFactoidsItem: два span или два p
    for item in soup.find_all(attrs={'data-name': 'ObjectFactoidsItem'}):
        spans = item.find_all('span', recursive=True)
        if len(spans) >= 2:
            fl = _floor_from_label_value(spans[0].get_text(strip=True), spans[1].get_text(strip=True))
            if fl:
                return fl
        ps = item.find_all('p', recursive=True)
        if len(ps) >= 2:
            fl = _floor_from_label_value(ps[0].get_text(strip=True), ps[1].get_text(strip=True))
            if fl:
                return fl

    # 3) OfferSummaryInfoItem (как на карточке кратких сведений)
    for item in soup.find_all(attrs={'data-name': 'OfferSummaryInfoItem'}):
        spans = item.find_all('span', recursive=True)
        if len(spans) >= 2:
            fl = _floor_from_label_value(spans[0].get_text(strip=True), spans[1].get_text(strip=True))
            if fl:
                return fl
        ps = item.find_all('p', recursive=True)
        if len(ps) >= 2:
            fl = _floor_from_label_value(ps[0].get_text(strip=True), ps[1].get_text(strip=True))
            if fl:
                return fl

    # 4) Сырой HTML: часто в description / JSON на странице
    for m in re.finditer(r'этаж\s*(\d+)\s*/\s*(\d+)', html[:120000], re.I):
        a, b = int(m.group(1)), int(m.group(2))
        if 1 <= a <= 200 and 1 <= b <= 200 and a <= b:
            return f"{a}/{b}"

    # 5) Текст страницы
    text = soup.get_text(separator=' ', strip=True)[:20000]
    m = re.search(r'этаж[а]?\s*[:\s]*(\d+)\s*[/из]\s*(\d+)', text, re.I) or re.search(
        r'(\d+)\s*/\s*(\d+)\s*этаж', text, re.I
    )
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    # «на 4-м этаже … 18-ти этажного»
    m = re.search(r'на\s+(\d+)[-‐‑]м\s+этаже', text, re.I)
    m2 = re.search(r'(\d+)[-‐‑]ти\s+этажн', text, re.I)
    if m and m2:
        return f"{m.group(1)}/{m2.group(1)}"
    return None


def main():
    if not os.path.isfile(JSON_PATH):
        print(f"Файл не найден: {JSON_PATH}")
        return

    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        apartments = json.load(f)

    updated = 0
    skipped_has_floor = 0
    skipped_no_html = 0
    for apt in apartments:
        offer_id = extract_offer_id(apt.get('url', ''))
        if not offer_id:
            continue
        if apt.get('floor'):
            skipped_has_floor += 1
            continue
        img_src = apt.get('img_src') or ''
        html_path = resolve_html_path(offer_id, img_src)
        if not html_path:
            skipped_no_html += 1
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
    print(
        f"\nОбновлено этаж: {updated}. Уже был этаж (пропуск): {skipped_has_floor}. "
        f"Нет HTML: {skipped_no_html}. Всего записей: {len(apartments)}. Сохранён {JSON_PATH}."
    )

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
