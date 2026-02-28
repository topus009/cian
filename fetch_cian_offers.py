# -*- coding: utf-8 -*-
"""
Попытка скачать страницы объявлений Циан по ссылкам из apartments.json
и извлечь все фото + полное описание. Результат обновляет apartments.json.

Если запрос не удаётся (403, пустая страница, контент через JS) — сохраните
вручную HTML каждой квартиры (Файл → Сохранить как → «Веб-страница, полностью»)
в папку data/offers/ (например offer_324037941.html). Затем запустите:
  python parse_cian_offer_pages.py
"""
import json
import os
import re
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(SCRIPT_DIR, 'apartments.json')

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Установите: pip install requests beautifulsoup4")
    exit(1)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml',
    'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
}


def fetch_offer(url: str):
    """Скачать HTML страницы объявления."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        r.encoding = r.apparent_encoding or 'utf-8'
        return r.text
    except Exception as e:
        print(f"  Ошибка: {e}")
        return None


def extract_photos_and_description(html: str):
    """Извлечь URL фото и полное описание из HTML объявления Циан."""
    if not html:
        return [], ''
    soup = BeautifulSoup(html, 'html.parser')
    photos = []
    description = ''

    # 1) Фото часто в JSON внутри script (next/data, __NEXT_DATA__, или window.__initialData__)
    for script in soup.find_all('script', type='application/json'):
        text = script.string or ''
        # Ищем URL картинок cdn-cian или static
        urls = re.findall(r'https?://[^"\\]+?\.(?:cdn-cian\.ru|static\.cdn-cian\.ru)[^"\\]*', text)
        photos.extend(urls)
    for script in soup.find_all('script'):
        if not script.string:
            continue
        urls = re.findall(r'https?://[^"\\]+?\.(?:cdn-cian\.ru|static\.cdn-cian\.ru)[^"\\]*\.(?:jpg|jpeg|png|webp)', script.string, re.I)
        photos.extend(urls)

    # 2) img с data-src или src
    for img in soup.find_all('img', src=True):
        s = img.get('data-src') or img.get('src') or ''
        if 'cdn-cian' in s or 'photo' in s.lower() or 'image' in s.lower():
            if s not in photos:
                photos.append(s)
    for img in soup.find_all('img', {'data-src': True}):
        s = img['data-src']
        if s not in photos:
            photos.append(s)

    # 3) Описание — часто в [data-name="description"] или itemProp="description"
    desc_el = soup.find(attrs={'data-name': 'description'}) or soup.find(attrs={'itemprop': 'description'})
    if desc_el:
        description = desc_el.get_text(separator='\n', strip=True)
    if not description:
        for p in soup.find_all('p', class_=re.compile(r'description|text')):
            description += p.get_text(separator='\n', strip=True) + '\n'

    # Убираем дубликаты, оставляем порядок
    seen = set()
    unique_photos = []
    for u in photos:
        u = u.split('?')[0].rstrip('/')
        if u not in seen and ('photo' in u or 'image' in u or 'jpg' in u or 'jpeg' in u or 'png' in u or 'webp' in u):
            seen.add(u)
            unique_photos.append(u)

    return unique_photos[:30], description.strip()


def main():
    if not os.path.isfile(JSON_PATH):
        print(f"Сначала запустите parse_cian_favorites.py (нужен {JSON_PATH})")
        return

    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        apartments = json.load(f)

    updated = 0
    for i, apt in enumerate(apartments):
        url = apt.get('url', '')
        if not url or 'sale/flat' not in url:
            continue
        print(f"[{i+1}/{len(apartments)}] {url}")
        html = fetch_offer(url)
        if not html:
            print("  Пропуск (не удалось загрузить). Сохраните страницу вручную в data/offers/.")
            time.sleep(2)
            continue
        photos, desc = extract_photos_and_description(html)
        if photos:
            apt['photos'] = photos
            if not apt.get('img_src') and photos:
                apt['img_src'] = photos[0]
            updated += 1
            print(f"  Найдено фото: {len(photos)}")
        if desc and len(desc) > len(apt.get('description') or ''):
            apt['description'] = desc[:2000]
            print("  Обновлено описание.")
        time.sleep(1.5)

    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(apartments, f, ensure_ascii=False, indent=2)
    print(f"\nОбновлено квартир с фото: {updated}. Перезапустите create_map_cian.py для обновления карты.")


if __name__ == '__main__':
    main()
