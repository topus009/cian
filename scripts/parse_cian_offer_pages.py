# -*- coding: utf-8 -*-
"""
Парсит сохранённые HTML страницы объявлений Циан:
- из data/<ID>.html и data/<ID>_files/ (первые 15 квартир),
- из data/static_2/<ID>.html и data/static_2/<ID>_files/ (вторая пачка, 18 квартир).
Для каждой квартиры: JSON-LD (описание, цена, название), meta (площадь, этаж), фото из соответствующей папки.
Обновляет запись в data/apartments.json.
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
STATIC_2_DIR = os.path.join(ROOT, 'data', 'static_2')

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


def collect_local_photos_static2(offer_id: str):
    """Собрать фото из data/static_2/<ID>_files/ (для второй пачки квартир)."""
    folder = os.path.join(STATIC_2_DIR, offer_id + '_files')
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
        rel = 'data/static_2/' + offer_id + '_files/' + name.replace('\\', '/')
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
            # Общая площадь из названия: "41,6 м²" или "36 м²"
            name = out['title']
            ma = re.search(r'([\d,\.]+)\s*м\s*²', name) or re.search(r'([\d,\.]+)\s*м²', name)
            if ma:
                try:
                    v = float(ma.group(1).replace(',', '.'))
                    if 15 <= v <= 200:
                        out['total_area'] = str(int(v)) if v == int(v) else str(round(v, 1))
                except ValueError:
                    pass
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
    """Площадь, этаж, цена, адрес из meta og:title и <title>."""
    out = {}
    og = soup.find('meta', property='og:title')
    title_str = None
    if og and og.get('content'):
        title_str = og['content'].strip()
    if not title_str:
        t_tag = soup.find('title')
        if t_tag and t_tag.string:
            title_str = t_tag.string.strip()
    if title_str:
        t = title_str
        m_price = re.search(r'за\s+([\d\s]+)\s*руб', t, re.I)
        if m_price:
            out['price_str'] = m_price.group(1).replace(' ', '') + ' ₽'
        # Площадь: только число, похожее на общую (15–200 м²), чтобы не захватить площадь комнаты/кухни (4, 8, 12)
        m_area = re.search(r'([\d,.]+)\s*(?:м\.?кв\.?|м²)', t, re.I)
        if m_area:
            raw = m_area.group(1).replace(',', '.')
            try:
                val = float(raw)
                if 15 <= val <= 200:
                    out['total_area'] = str(int(val)) if val == int(val) else str(round(val, 1))
            except ValueError:
                pass
        m_floor = re.search(r'этаж\s+(\d+/\d+)', t, re.I)
        if m_floor:
            out['floor'] = m_floor.group(1)
        # Адрес только из <title> (в og:title адреса нет)
        title_full = None
        t_tag = soup.find('title')
        if t_tag and t_tag.string:
            title_full = t_tag.string.strip()
        if title_full:
            m_addr = re.search(r'[\d,.]+\s*(?:м\.?кв\.?|м²)\s*(.+?)\s*-\s*база', title_full, re.I | re.DOTALL)
        else:
            m_addr = re.search(r'[\d,.]+\s*(?:м\.?кв\.?|м²)\s*(.+?)\s*-\s*база', t, re.I | re.DOTALL)
        if m_addr:
            addr = re.sub(r'\s+', ' ', m_addr.group(1).strip()).strip().strip(',')
            if addr and len(addr) > 10 and 'Санкт-Петербург' in addr:
                out['address'] = addr[:300]
    desc = soup.find('meta', attrs={'name': 'description'})
    if desc and desc.get('content') and 'total_area' not in out:
        m = re.search(r'площадью\s+([\d,.\s]+?)\s*м', desc['content'], re.I)
        if m:
            raw = m.group(1).replace(',', '.').replace(' ', '').strip()
            try:
                val = float(raw)
                if 15 <= val <= 200:
                    out['total_area'] = str(int(val)) if val == int(val) else str(round(val, 1))
            except ValueError:
                pass
    return out


def extract_build_year(text: str):
    """Извлечь год постройки из текста (описание, страница). Несколько вариантов формулировок."""
    if not text or not isinstance(text, str):
        return None
    text = re.sub(r'\s+', ' ', text)
    patterns = [
        r'(\d{4})\s*года?\s*постройки',
        r'построен[а]?\s*в\s*(\d{4})',
        r'(\d{4})\s*год[а]?\s*постройки',
        r'дом[а]?\s*(\d{4})\s*год',
        r'(\d{4})\s*г\.?\s*постройки',
        r'в\s*(\d{4})\s*год',
        r'(\d{4})\s*год[а]?\s*постройки',
        r'постройки\s*(\d{4})',
        r'год[а]?\s*постройки[^\d]*(\d{4})',
        r'\b(19\d{2}|20\d{2})\s*год\b',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            y = int(m.group(1))
            if 1950 <= y <= 2030:
                return y
    return None


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
    # Год постройки: из описания и из всего HTML (на странице Циан часто указан в блоке характеристик)
    combined = (out.get('description') or '') + ' ' + (out.get('title') or '')
    year = extract_build_year(combined)
    if year is None and soup:
        body_text = soup.get_text(separator=' ')[:8000]
        year = extract_build_year(body_text)
    if year is not None:
        out['build_year'] = year
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

    # Файлы из data/<ID>.html (первые 15) и data/static_2/<ID>.html (вторая пачка, 18 шт.)
    files_by_id = {}
    for name in os.listdir(DATA_DIR):
        m = re.match(r'^(\d+)\.html$', name)
        if m:
            offer_id = m.group(1)
            path = os.path.join(DATA_DIR, name)
            if os.path.isfile(path):
                files_by_id[offer_id] = (path, 'root')
    if os.path.isdir(STATIC_2_DIR):
        for name in os.listdir(STATIC_2_DIR):
            m = re.match(r'^(\d+)\.html$', name)
            if m:
                offer_id = m.group(1)
                if offer_id in files_by_id:
                    continue
                path = os.path.join(STATIC_2_DIR, name)
                if os.path.isfile(path):
                    files_by_id[offer_id] = (path, 'static_2')

    if not files_by_id:
        print(f"В data/ и data/static_2/ нет файлов вида <ID>.html")
        return

    print(f"Найдено HTML: {len(files_by_id)} (data/ + static_2/). Квартир в JSON: {len(by_id)}.")

    updated_any = 0
    for offer_id, (filepath, source) in files_by_id.items():
        if offer_id not in by_id:
            print(f"  Пропуск {offer_id}: нет в apartments.json")
            continue
        apt = by_id[offer_id]
        changed = False

        # 1) Локальные фото: из data/<ID>_files/ или data/static_2/<ID>_files/
        if source == 'static_2':
            local_photos = collect_local_photos_static2(offer_id)
            photo_note = 'static_2/' + offer_id + '_files/'
        else:
            local_photos = collect_local_photos(offer_id)
            photo_note = offer_id + '_files/'
        if local_photos:
            apt['photos'] = local_photos
            apt['img_src'] = local_photos[0]
            changed = True
            print(f"  {offer_id}: {len(local_photos)} фото из {photo_note}")

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
            else:
                apt['price'] = str(parsed['price_value']) + ' ₽'
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
        if parsed.get('address'):
            apt['address'] = parsed['address'][:300]
            changed = True
        if parsed.get('build_year') is not None:
            apt['build_year'] = parsed['build_year']
            changed = True

        if changed:
            updated_any += 1

    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(apartments, f, ensure_ascii=False, indent=2)
    print(f"Обновлено квартир: {updated_any}. Запустите: python scripts/create_map_cian.py")


if __name__ == '__main__':
    main()
