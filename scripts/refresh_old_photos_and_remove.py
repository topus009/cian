# -*- coding: utf-8 -*-
"""
1) Удалить 3 квартиры (объявления сняты с публикации, картинки скачались неправильно):
   324642095, 322716647, 324800212 — из apartments.json и из data/static_4/.

2) Для «старых» квартир (те, у которых фото не в static_4 — было до парсера по 53 ссылкам):
   перечитать их сохранённый HTML, вытащить URL картинок (-2 -> -1), перекачать в те же папки,
   удалить старые картинки, обновить photos и img_src в JSON.
   Сначала пробуем requests; если не скачалось — через Chrome (Selenium): открываем страницу
   объявления, берём URL картинок из DOM, скачиваем каждую через fetch() в контексте страницы.

Запуск из корня: python scripts/refresh_old_photos_and_remove.py
"""
import base64
import json
import os
import re
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
JSON_PATH = os.path.join(ROOT, 'data', 'apartments.json')
DATA_DIR = os.path.join(ROOT, 'data')
STATIC_2_DIR = os.path.join(ROOT, 'data', 'static_2')
STATIC_3_DIR = os.path.join(ROOT, 'data', 'static_3')

REMOVE_IDS = {'324642095', '322716647', '324800212'}

sys.path.insert(0, SCRIPT_DIR)
from fetch_cian_offers_by_data_name import (
    extract_offer_id,
    parse_offer_page,
    HEADERS,
    filename_from_url,
)
import requests
from bs4 import BeautifulSoup

SELENIUM_AVAILABLE = False
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import InvalidSessionIdException, WebDriverException
    SELENIUM_AVAILABLE = True
except ImportError:
    pass

# Заголовки для запросов к CDN Циан (часто проверяют Referer)
IMAGE_HEADERS = {
    **HEADERS,
    'Referer': 'https://spb.cian.ru/',
    'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
}


# --- Selenium (опционально): загрузка фото через браузер ---
def _create_driver():
    if not SELENIUM_AVAILABLE:
        return None
    opts = Options()
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    opts.add_argument("--window-size=1280,900")
    try:
        return webdriver.Chrome(options=opts)
    except Exception:
        return None


def _is_captcha_page(html):
    if not html:
        return True
    return "Captcha" in html and "smartcaptcha" in html.lower()


def _wait_for_offer_page(driver, timeout_sec=60):
    try:
        WebDriverWait(driver, timeout_sec).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-name='OfferTitleNew'], [data-name='OfferCardPageLayoutCenter'], [data-name='PriceInfo']"))
        )
        return True
    except Exception:
        return False


def _fetch_html_with_browser(driver, url):
    """Открыть url в браузере, при капче ждать Enter, вернуть HTML."""
    driver.get(url)
    time.sleep(1)
    html = driver.page_source
    if not _is_captcha_page(html):
        if _wait_for_offer_page(driver, timeout_sec=8):
            return driver.page_source
        time.sleep(2)
        return driver.page_source
    print("    Капча. Решите в Chrome и нажмите Enter здесь.")
    input("    Enter после решения капчи... ")
    time.sleep(1)
    if _is_captcha_page(driver.page_source):
        return None
    _wait_for_offer_page(driver, timeout_sec=12)
    return driver.page_source


def _download_one_image_via_browser(driver, url):
    """Скачать одну картинку через fetch() в контексте страницы, вернуть (bytes, ext) или None."""
    try:
        data_url = driver.execute_async_script("""
            var url = arguments[0];
            var done = arguments[1];
            fetch(url, { credentials: 'same-origin' })
                .then(r => r.blob())
                .then(blob => {
                    var r = new FileReader();
                    r.onload = () => done(r.result);
                    r.readAsDataURL(blob);
                })
                .catch(() => done(null));
        """, url)
        if not data_url or not data_url.startswith("data:"):
            return None
        # data:image/jpeg;base64,XXXX
        head, b64 = data_url.split(",", 1)
        ext = ".jpg"
        if "image/png" in head:
            ext = ".png"
        elif "image/webp" in head:
            ext = ".webp"
        return (base64.b64decode(b64), ext)
    except Exception:
        return None


def download_images_via_browser(driver, offer_id, image_urls, folder, path_prefix):
    """Скачать картинки через браузер (fetch в контексте страницы). Вернуть список путей."""
    image_urls = [u for u in (image_urls or []) if _is_absolute_image_url(u)]
    if not image_urls:
        return []
    os.makedirs(folder, exist_ok=True)
    local_paths = []
    for i, url in enumerate(image_urls[:50]):
        result = _download_one_image_via_browser(driver, url)
        if not result:
            time.sleep(0.1)
            continue
        raw, ext = result
        name = filename_from_url(url)
        if not name.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
            name = f"image_{i+1}{ext}"
        filepath = os.path.join(folder, name)
        with open(filepath, 'wb') as f:
            f.write(raw)
        rel = f"{path_prefix}/{offer_id}_files/{name}".replace("\\", "/")
        local_paths.append(rel)
        time.sleep(0.05)
    return local_paths


def _is_absolute_image_url(u):
    """Только абсолютные URL (в сохранённом HTML JSON-LD часто переписан в относительные)."""
    if not u:
        return False
    u = u.strip()
    return u.startswith('http://') or u.startswith('https://') or u.startswith('//')


def _normalize_image_url(u):
    """-2 -> -1, // -> https:."""
    u = str(u).strip()
    if re.search(r'-\d+\.(jpg|jpeg|png|webp)$', u, re.I):
        u = re.sub(r'-(\d+)(\.(jpg|jpeg|png|webp))$', r'-1\2', u, flags=re.I)
    if u.startswith('//'):
        u = 'https:' + u
    return u


def extract_image_urls_from_html_cdn(html):
    """Вытащить все абсолютные URL картинок cdn-cian из HTML (meta og:image, ссылки в тексте)."""
    seen = set()
    out = []
    # og:image
    for m in re.finditer(r'content=["\'](https?://[^"\']+?\.(?:jpg|jpeg|png|webp))["\']', html, re.I):
        u = m.group(1)
        if 'cdn-cian' in u and u not in seen:
            seen.add(u)
            out.append(_normalize_image_url(u))
    # любые https://images.cdn-cian.ru/... изображения
    for m in re.finditer(r'https://images\.cdn-cian\.ru/[^\s"\'<>]+?\.(?:jpg|jpeg|png|webp)', html, re.I):
        u = m.group(0).split('?')[0].rstrip('.,;:)')
        if u not in seen:
            seen.add(u)
            out.append(_normalize_image_url(u))
    return out[:50]


def extract_image_urls_from_ldjson(html):
    """Из старых HTML (без data-name) вытащить URL картинок из script type=application/ld+json.
    Учитываем, что в сохранённом HTML ссылки могли стать относительными (./id_files/...) — такие пропускаем.
    """
    # Захват до </script>, т.к. в description может быть символ <
    m = re.search(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>\s*(.+?)\s*</script>',
        html, re.I | re.DOTALL
    )
    if m:
        try:
            data = json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            data = None
        if data:
            items = []
            if data.get('@type') == 'Product':
                items.append(data)
            if data.get('@graph'):
                for item in data['@graph']:
                    if isinstance(item, dict) and item.get('@type') == 'Product':
                        items.append(item)
            if items:
                obj = items[0]
                imgs = obj.get('image')
                if imgs:
                    if isinstance(imgs, str):
                        imgs = [imgs]
                    out = []
                    for u in imgs[:50]:
                        u = str(u).strip()
                        if not _is_absolute_image_url(u) or 'cdn-cian' not in u:
                            continue
                        u = _normalize_image_url(u)
                        out.append(u)
                    if out:
                        return out
    # Fallback: BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    for script in soup.find_all('script', type='application/ld+json'):
        content = script.string or (script.next_element if hasattr(script, 'next_element') and script.next_element else None)
        if not content and script.contents:
            content = ''.join(getattr(c, 'string', str(c)) for c in script.contents)
        if not content:
            continue
        try:
            data = json.loads(content.strip() if isinstance(content, str) else content)
        except (json.JSONDecodeError, TypeError):
            continue
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
        imgs = obj.get('image')
        if not imgs:
            continue
        if isinstance(imgs, str):
            imgs = [imgs]
        out = []
        for u in imgs[:50]:
            u = str(u).strip()
            if not _is_absolute_image_url(u) or 'cdn-cian' not in u:
                continue
            u = _normalize_image_url(u)
            out.append(u)
        if out:
            return out
    return []


def remove_three_apartments(apartments):
    """Удалить записи с id из REMOVE_IDS."""
    return [a for a in apartments if extract_offer_id(a.get('url', '')) not in REMOVE_IDS]


def delete_static_4_for(offer_id):
    """Удалить data/static_4/<id>.html и data/static_4/<id>_files/."""
    base = os.path.join(ROOT, 'data', 'static_4')
    html_path = os.path.join(base, offer_id + '.html')
    folder = os.path.join(base, offer_id + '_files')
    if os.path.isfile(html_path):
        os.remove(html_path)
    if os.path.isdir(folder):
        for name in os.listdir(folder):
            os.remove(os.path.join(folder, name))
        os.rmdir(folder)


def get_html_path(offer_id, img_src):
    """По img_src определить, где лежит HTML: data/, static_2/, static_3/."""
    if not img_src:
        return None
    if 'static_2/' in img_src:
        return os.path.join(STATIC_2_DIR, offer_id + '.html')
    if 'static_3/' in img_src:
        return os.path.join(STATIC_3_DIR, offer_id + '.html')
    return os.path.join(DATA_DIR, offer_id + '.html')


def get_photos_folder_and_prefix(img_src, offer_id):
    """Вернуть (абсолютный путь к папке _files, префикс для путей в JSON)."""
    if not img_src:
        return None, None
    if 'static_2/' in img_src:
        folder = os.path.join(STATIC_2_DIR, offer_id + '_files')
        prefix = 'data/static_2'
        return folder, prefix
    if 'static_3/' in img_src:
        folder = os.path.join(STATIC_3_DIR, offer_id + '_files')
        prefix = 'data/static_3'
        return folder, prefix
    folder = os.path.join(DATA_DIR, offer_id + '_files')
    return folder, 'data'


def clear_folder_images(folder):
    """Удалить все файлы изображений из папки."""
    if not os.path.isdir(folder):
        return
    for name in os.listdir(folder):
        if name.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
            try:
                os.remove(os.path.join(folder, name))
            except OSError:
                pass


def download_images_to_folder(offer_id, image_urls, folder, path_prefix):
    """Скачать картинки в folder, вернуть список путей path_prefix/offer_id_files/name."""
    # только абсолютные URL (в сохранённом HTML могли попасть относительные)
    image_urls = [u for u in (image_urls or []) if _is_absolute_image_url(u)]
    if not image_urls:
        return []
    os.makedirs(folder, exist_ok=True)
    local_paths = []
    for i, url in enumerate(image_urls[:50]):
        for attempt in range(3):
            try:
                r = requests.get(url, headers=IMAGE_HEADERS, timeout=20)
                r.raise_for_status()
                name = filename_from_url(url)
                if not name.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                    name = f'image_{i+1}.jpg'
                filepath = os.path.join(folder, name)
                with open(filepath, 'wb') as f:
                    f.write(r.content)
                rel = f"{path_prefix}/{offer_id}_files/{name}".replace('\\', '/')
                local_paths.append(rel)
                break
            except Exception as e:
                if attempt == 2 and not local_paths:
                    print(f"    (пример ошибки для {offer_id}: {e})")
                time.sleep(0.3 * (attempt + 1))
        time.sleep(0.08)
    return local_paths


def main():
    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        apartments = json.load(f)

    # 1) Удалить 3 квартиры
    n_before = len(apartments)
    apartments = remove_three_apartments(apartments)
    for oid in REMOVE_IDS:
        delete_static_4_for(oid)
    print(f"Удалены квартиры {REMOVE_IDS}, записей: {n_before} -> {len(apartments)}")

    # 2) Старые квартиры — у которых img_src не содержит static_4
    old_apartments = [a for a in apartments if 'static_4' not in (a.get('img_src') or '')]
    print(f"Старых квартир (перекачать фото): {len(old_apartments)}")
    if old_apartments and SELENIUM_AVAILABLE:
        print("При неудаче requests будет использован Chrome (Selenium).")

    driver = None
    for apt in old_apartments:
        offer_id = extract_offer_id(apt.get('url', ''))
        if not offer_id:
            continue
        img_src = apt.get('img_src') or ''
        html_path = get_html_path(offer_id, img_src)
        if not html_path or not os.path.isfile(html_path):
            print(f"  {offer_id}: нет HTML {html_path}")
            continue
        folder, path_prefix = get_photos_folder_and_prefix(img_src, offer_id)
        if not folder:
            continue
        with open(html_path, 'r', encoding='utf-8', errors='replace') as f:
            html = f.read()
        parsed = parse_offer_page(html, apt.get('url', ''))
        image_urls = parsed.get('image_urls', [])
        if not image_urls:
            image_urls = extract_image_urls_from_ldjson(html)
        if not image_urls:
            image_urls = extract_image_urls_from_html_cdn(html)
        if not image_urls:
            print(f"  {offer_id}: в HTML нет URL картинок")
            continue
        clear_folder_images(folder)
        local_paths = download_images_to_folder(offer_id, image_urls, folder, path_prefix)
        if not local_paths and SELENIUM_AVAILABLE:
            if driver is None:
                print("  Запуск Chrome для загрузки фото через браузер...")
                driver = _create_driver()
            if driver:
                try:
                    page_html = _fetch_html_with_browser(driver, apt.get('url', ''))
                    if page_html and not _is_captcha_page(page_html):
                        live_parsed = parse_offer_page(page_html, apt.get('url', ''))
                        live_urls = live_parsed.get('image_urls', [])
                        if live_urls:
                            local_paths = download_images_via_browser(driver, offer_id, live_urls, folder, path_prefix)
                except (InvalidSessionIdException, WebDriverException):
                    try:
                        if driver:
                            driver.quit()
                    except Exception:
                        pass
                    driver = None
        if local_paths:
            apt['photos'] = local_paths
            apt['img_src'] = local_paths[0]
            print(f"  {offer_id}: перекачано {len(local_paths)} фото")
        else:
            print(f"  {offer_id}: не удалось скачать фото")
        time.sleep(0.15)

    if driver:
        try:
            driver.quit()
        except Exception:
            pass

    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(apartments, f, ensure_ascii=False, indent=2)
    print("Сохранён apartments.json.")

    # Перегенерировать apartments.js для карты/списка (чтобы в HTML отображалось актуальное число квартир)
    try:
        import subprocess
        r = subprocess.run(
            [sys.executable, os.path.join(SCRIPT_DIR, "create_map_cian.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r.returncode == 0:
            print(r.stdout.strip() if r.stdout else "Обновлён data/apartments.js")
        else:
            print("Запустите вручную: python scripts/create_map_cian.py")
    except Exception as e:
        print(f"Не удалось вызвать create_map_cian: {e}. Запустите: python scripts/create_map_cian.py")


if __name__ == '__main__':
    main()
