# -*- coding: utf-8 -*-
"""
Парсер объявлений Циан по списку URL.

Делает GET-запрос по каждой ссылке, разбирает HTML по data-name атрибутам:
- OfferCardPageLayoutCenter — контейнер
- OfferTitleNew — заголовок
- PriceInfo — цена
- OfferFactItem — цена за кв. м
- AddressContainer — адрес
- ObjectFactoids — блок с этажом, площадью, годом постройки
- PaginationThumbsComponent — контейнер миниатюр
- ThumbComponent — блок картинки (ссылка; -2 в конце заменяем на -1 для полного размера)

Скачивает HTML в data/static_4/<ID>.html, картинки в data/static_4/<ID>_files/.
Добавляет/обновляет записи в data/apartments.json.

Запуск из корня проекта:
  python scripts/fetch_cian_offers_by_data_name.py
  python scripts/fetch_cian_offers_by_data_name.py data/urls_to_fetch.txt

Сначала без кук; при блокировке можно передать заголовки с куками.
"""
import json
import os
import re
import time
import sys
from urllib.parse import urljoin

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
JSON_PATH = os.path.join(ROOT, 'data', 'apartments.json')
STATIC_4_DIR = os.path.join(ROOT, 'data', 'static_4')
DEFAULT_URLS_FILE = os.path.join(ROOT, 'data', 'urls_to_fetch.txt')

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Установите: pip install requests beautifulsoup4")
    sys.exit(1)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
}


def extract_offer_id(url: str):
    m = re.search(r'sale/flat/(\d+)', url)
    return m.group(1) if m else None


def fetch_html(url: str, headers=None):
    h = headers or HEADERS
    try:
        r = requests.get(url, headers=h, timeout=20)
        r.raise_for_status()
        r.encoding = r.apparent_encoding or 'utf-8'
        return r.text
    except Exception as e:
        return None


def find_by_data_name(soup, name, root=None):
    """Найти элемент с data-name (в root или во всей странице)."""
    base = root or soup
    el = base.find(attrs={'data-name': name})
    if el is None:
        el = soup.find(attrs={'data-name': name})
    return el


def find_all_by_data_name(soup, name, root=None):
    base = root or soup
    return base.find_all(attrs={'data-name': name}) or soup.find_all(attrs={'data-name': name})


def parse_price_info(el):
    """Из блока PriceInfo извлечь число цены."""
    if not el:
        return None
    text = el.get_text(strip=True) or ''
    text = re.sub(r'\s+', '', text)
    m = re.search(r'(\d[\d\s]*\d|\d+)', text)
    if m:
        try:
            return int(m.group(1).replace(' ', ''))
        except ValueError:
            pass
    return None


def parse_price_per_sqm(el):
    """OfferFactItem — цена за кв. м (обычно текст типа «208 333 ₽/м²»)."""
    if not el:
        return None
    text = el.get_text(strip=True) or ''
    m = re.search(r'([\d\s]+)\s*₽', text)
    if m:
        try:
            return int(m.group(1).replace(' ', ''))
        except ValueError:
            pass
    return None


def parse_object_factoids(container):
    """Из блока ObjectFactoids: этаж, площадь, год постройки (текст контейнера и потомков)."""
    out = {}
    if not container:
        return out
    text = container.get_text(separator=' ', strip=True) if hasattr(container, 'get_text') else ''
    # Несколько блоков с data-name ObjectFactoids внутри одного контейнера
    if hasattr(container, 'find_all'):
        for el in container.find_all(attrs={'data-name': 'ObjectFactoids'}):
            text += ' ' + (el.get_text(separator=' ', strip=True) or '')
    if not text:
        return out
    m_floor = re.search(r'этаж[а]?\s*[:\s]*(\d+)\s*[/из]\s*(\d+)', text, re.I) or re.search(r'(\d+)\s*/\s*(\d+)\s*этаж', text, re.I)
    if m_floor:
        out['floor'] = f"{m_floor.group(1)}/{m_floor.group(2)}"
    m_area = re.search(r'(?:общая\s+)?площадь[^\d]*([\d,\.]+)\s*м', text, re.I) or re.search(r'([\d,\.]+)\s*м\s*²', text, re.I)
    if m_area:
        try:
            v = float(m_area.group(1).replace(',', '.').strip())
            if 10 <= v <= 300:
                out['total_area'] = str(int(v)) if v == int(v) else str(round(v, 1))
        except ValueError:
            pass
    m_year = re.search(r'(?:год[а]?\s+постройки|постройки)\s*[:\s]*(\d{4})', text, re.I) or re.search(r'(\d{4})\s*г\.?\s*постройки', text, re.I)
    if m_year:
        y = int(m_year.group(1))
        if 1950 <= y <= 2035:
            out['build_year'] = y
    return out


def image_url_to_full_size(url: str):
    """Заменить в конце URL -2 на -1 для полного размера картинки."""
    if not url:
        return url
    url = url.split('?')[0].rstrip('/')
    if url.endswith('-2') or re.search(r'-\d+\.(jpg|jpeg|png|webp)$', url, re.I):
        url = re.sub(r'-(\d+)(\.(jpg|jpeg|png|webp))$', r'-1\2', url, flags=re.I)
    return url


def collect_image_urls(soup, root=None):
    """Собрать URL картинок из PaginationThumbsComponent -> ThumbComponent, заменить -2 на -1."""
    base = root or soup
    thumbs_container = find_by_data_name(soup, 'PaginationThumbsComponent', base)
    if not thumbs_container:
        thumbs_container = soup
    thumb_blocks = find_all_by_data_name(soup, 'ThumbComponent', thumbs_container)
    urls = []
    seen = set()
    for block in thumb_blocks:
        for img in block.find_all('img'):
            src = img.get('data-src') or img.get('src')
            if src and ('cdn-cian' in src or 'photo' in src or '.jpg' in src.lower() or '.jpeg' in src.lower() or '.webp' in src.lower()):
                full = image_url_to_full_size(src)
                if full and full not in seen:
                    seen.add(full)
                    urls.append(full)
        for a in block.find_all('a', href=True):
            href = a.get('href')
            if href and ('.jpg' in href.lower() or '.jpeg' in href.lower() or '.webp' in href.lower() or 'photo' in href):
                full = image_url_to_full_size(urljoin('https://spb.cian.ru', href))
                if full and full not in seen:
                    seen.add(full)
                    urls.append(full)
    container = find_by_data_name(soup, 'OfferCardPageLayoutCenter')
    if container and not urls:
        for img in container.find_all('img', src=True):
            src = img.get('data-src') or img.get('src')
            if src and ('cdn-cian' in src or 'static.cian' in src):
                full = image_url_to_full_size(src)
                if full and full not in seen:
                    seen.add(full)
                    urls.append(full)
    return urls


def parse_offer_page(html: str, url: str):
    """Распарсить одну страницу объявления по data-name."""
    soup = BeautifulSoup(html, 'html.parser')
    container = find_by_data_name(soup, 'OfferCardPageLayoutCenter')
    root = container or soup

    title_el = find_by_data_name(soup, 'OfferTitleNew', root)
    title = title_el.get_text(strip=True) if title_el else ''

    price_el = find_by_data_name(soup, 'PriceInfo', root)
    price_value = parse_price_info(price_el)
    price_str = (price_el.get_text(strip=True) if price_el else '').strip() if price_el else ''
    if not price_str and price_value:
        price_str = f"{price_value} ₽"

    price_per_sqm = None
    for el in find_all_by_data_name(soup, 'OfferFactItem', root):
        if 'м²' in (el.get_text() or ''):
            price_per_sqm = parse_price_per_sqm(el)
            break

    address_el = find_by_data_name(soup, 'AddressContainer', root)
    address = address_el.get_text(separator=' ', strip=True) if address_el else ''

    factoids_el = find_by_data_name(soup, 'ObjectFactoids', root)
    facts = parse_object_factoids(factoids_el)
    if not facts.get('total_area') and title:
        m = re.search(r'([\d,\.]+)\s*м\s*²', title, re.I) or re.search(r'([\d,\.]+)\s*м²', title, re.I)
        if m:
            try:
                v = float(m.group(1).replace(',', '.'))
                if 10 <= v <= 300:
                    facts['total_area'] = str(int(v)) if v == int(v) else str(round(v, 1))
            except ValueError:
                pass
    if price_value and facts.get('total_area') and not price_per_sqm:
        try:
            price_per_sqm = round(price_value / float(facts['total_area'].replace(',', '.')))
        except (ValueError, TypeError):
            pass

    image_urls = collect_image_urls(soup, root)

    return {
        'title': title[:500] if title else '',
        'price': price_str[:50] if price_str else (f'{price_value} ₽' if price_value else ''),
        'price_value': price_value,
        'address': address[:400] if address else '',
        'total_area': facts.get('total_area'),
        'floor': facts.get('floor'),
        'build_year': facts.get('build_year'),
        'price_per_sqm': price_per_sqm,
        'image_urls': image_urls,
    }


def filename_from_url(url: str):
    url = url.split('?')[0]
    name = url.rstrip('/').split('/')[-1]
    name = re.sub(r'-(\d+)(\.(jpg|jpeg|png|webp))$', r'-1\2', name, flags=re.I)
    return name or 'image.jpg'


def download_images(offer_id: str, image_urls: list, static_dir: str):
    if not image_urls:
        return []
    folder = os.path.join(static_dir, offer_id + '_files')
    os.makedirs(folder, exist_ok=True)
    local_paths = []
    for i, url in enumerate(image_urls[:50]):
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.raise_for_status()
            name = filename_from_url(url)
            if not name.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                name = f"image_{i+1}.jpg"
            filepath = os.path.join(folder, name)
            with open(filepath, 'wb') as f:
                f.write(r.content)
            rel = f"data/static_4/{offer_id}_files/{name}".replace('\\', '/')
            local_paths.append(rel)
        except Exception:
            pass
        time.sleep(0.05)
    return local_paths


def build_apartment_record(offer_id: str, url: str, parsed: dict, local_photos: list):
    return {
        'url': url,
        'title': parsed.get('title') or f'Квартира {offer_id}',
        'price': parsed.get('price') or '',
        'address': parsed.get('address') or '',
        'metro': [],
        'phone': '',
        'img_src': local_photos[0] if local_photos else '',
        'description': '',
        'photos': local_photos,
        'lat': None,
        'lon': None,
        'price_value': parsed.get('price_value'),
        'total_area': parsed.get('total_area'),
        'floor': parsed.get('floor'),
        'price_per_sqm': parsed.get('price_per_sqm'),
        'build_year': parsed.get('build_year'),
    }


def main():
    urls_file = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URLS_FILE
    if not os.path.isfile(urls_file):
        print(f"Файл со ссылками не найден: {urls_file}")
        sys.exit(1)

    with open(urls_file, 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip() and line.strip().startswith('http')]

    seen_ids = set()
    unique_urls = []
    for u in urls:
        oid = extract_offer_id(u)
        if oid and oid not in seen_ids:
            seen_ids.add(oid)
            unique_urls.append(u)

    print(f"Загружено {len(unique_urls)} уникальных URL из {urls_file}")

    os.makedirs(STATIC_4_DIR, exist_ok=True)

    if os.path.isfile(JSON_PATH):
        with open(JSON_PATH, 'r', encoding='utf-8') as f:
            apartments = json.load(f)
    else:
        apartments = []

    by_id = {}
    for apt in apartments:
        oid = extract_offer_id(apt.get('url', ''))
        if oid:
            by_id[oid] = apt

    added = 0
    updated = 0
    errors = 0

    for i, url in enumerate(unique_urls):
        offer_id = extract_offer_id(url)
        if not offer_id:
            continue
        print(f"[{i+1}/{len(unique_urls)}] {offer_id} ... ", end='', flush=True)
        html = fetch_html(url)
        if not html:
            print("не удалось загрузить")
            errors += 1
            time.sleep(1)
            continue

        parsed = parse_offer_page(html, url)
        image_urls = parsed.pop('image_urls', [])

        html_path = os.path.join(STATIC_4_DIR, offer_id + '.html')
        with open(html_path, 'w', encoding='utf-8', errors='replace') as f:
            f.write(html)

        local_photos = download_images(offer_id, image_urls, STATIC_4_DIR)
        if not local_photos and image_urls:
            print(f"картинки не скачались ({len(image_urls)} URL)", flush=True)
        else:
            print(f"HTML + {len(local_photos)} фото", flush=True)

        record = build_apartment_record(offer_id, url, parsed, local_photos)

        if offer_id in by_id:
            apt = by_id[offer_id]
            apt.update(record)
            updated += 1
        else:
            apartments.append(record)
            by_id[offer_id] = record
            added += 1

        time.sleep(0.5)

    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(apartments, f, ensure_ascii=False, indent=2)

    print(f"\nГотово. Добавлено: {added}, обновлено: {updated}, ошибок: {errors}.")
    print("Координаты (lat/lon) не заполнены — подставьте вручную или через geocode. Запустите: python scripts/create_map_cian.py")


if __name__ == '__main__':
    main()
