# -*- coding: utf-8 -*-
"""
Скачивание страниц объявлений Циан через реальный браузер Chrome (Selenium).

Открывает каждую ссылку в установленном Chrome — страница загружается как у пользователя,
капча отображается в окне: можно решить вручную, после этого скрипт сохранит HTML.

Использование:
  1. Установите: pip install selenium
  2. Chrome должен быть установлен (стандартный путь подхватится сам).
  3. Из корня проекта:
       python scripts/fetch_cian_offers_selenium.py
     или
       python scripts/fetch_cian_offers_selenium.py data/urls_to_fetch.txt

  Для каждой ссылки откроется вкладка, скрипт ждёт появления карточки объявления (до 60 сек).
  Если появилась капча — решите её в браузере, затем в консоли нажмите Enter по запросу скрипта.
  HTML сохраняется в data/static_4/<ID>.html, затем парсятся данные и качаются картинки.
"""
import json
import os
import re
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
STATIC_4_DIR = os.path.join(ROOT, 'data', 'static_4')
DEFAULT_URLS_FILE = os.path.join(ROOT, 'data', 'urls_to_fetch.txt')

# Парсинг и сохранение — из общего парсера (модуль в той же папке scripts)
sys.path.insert(0, SCRIPT_DIR)
from fetch_cian_offers_by_data_name import (
    JSON_PATH,
    extract_offer_id,
    parse_offer_page,
    download_images,
    build_apartment_record,
)

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import InvalidSessionIdException, WebDriverException
except ImportError:
    print("Установите Selenium: pip install selenium")
    sys.exit(1)


def is_captcha_page(html: str):
    if not html:
        return True
    return "Captcha" in html and "smartcaptcha" in html.lower()


def create_driver():
    """Chrome с видимым окном (чтобы можно было решить капчу)."""
    opts = Options()
    # Не headless — окно должно быть видно для капчи
    # opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    # Окно побольше, чтобы страница рендерилась нормально
    opts.add_argument("--window-size=1280,900")

    try:
        driver = webdriver.Chrome(options=opts)
    except Exception as e:
        print(f"Не удалось запустить Chrome: {e}")
        print("Убедитесь, что Chrome установлен. При необходимости укажите путь к chromedriver.")
        sys.exit(1)
    return driver


def wait_for_offer_page(driver, timeout_sec=60):
    """Ждём появления карточки объявления (любой из data-name)."""
    try:
        WebDriverWait(driver, timeout_sec).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-name='OfferTitleNew'], [data-name='OfferCardPageLayoutCenter'], [data-name='PriceInfo']"))
        )
        return True
    except Exception:
        return False


def fetch_html_with_browser(driver, url: str, wait_for_captcha_input=True):
    """
    Открыть url в браузере, при необходимости дождаться решения капчи, вернуть HTML.
    """
    driver.get(url)
    # Короткая пауза, дальше ждём появление карточки
    time.sleep(1)

    html = driver.page_source
    if not is_captcha_page(html):
        if wait_for_offer_page(driver, timeout_sec=8):
            return driver.page_source
        time.sleep(2)
        return driver.page_source

    # На странице капча — ждём, пока пользователь решит
    print("    Обнаружена капча. Решите её в открытом окне Chrome, затем перейдите сюда и нажмите Enter.")
    input("    Нажмите Enter после решения капчи... ")
    time.sleep(1)
    html = driver.page_source
    if is_captcha_page(html):
        print("    Всё ещё капча — попробуйте ещё раз или пропустите эту ссылку.")
        return None
    if not wait_for_offer_page(driver, timeout_sec=12):
        time.sleep(1)
    return driver.page_source


def save_progress(apartments, path=JSON_PATH):
    """Сохранить текущий список квартир в JSON (на случай обрыва браузера)."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(apartments, f, ensure_ascii=False, indent=2)


def main():
    urls_file = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URLS_FILE
    if not os.path.isfile(urls_file):
        print(f"Файл со ссылками не найден: {urls_file}")
        sys.exit(1)

    with open(urls_file, "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip() and line.strip().startswith("http")]

    seen = set()
    unique_urls = []
    for u in urls:
        oid = extract_offer_id(u)
        if oid and oid not in seen:
            seen.add(oid)
            unique_urls.append(u)

    print(f"Загружено {len(unique_urls)} уникальных URL. Запуск Chrome...")
    os.makedirs(STATIC_4_DIR, exist_ok=True)

    if os.path.isfile(JSON_PATH):
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            apartments = json.load(f)
    else:
        apartments = []

    by_id = {extract_offer_id(a.get("url", "")): a for a in apartments if extract_offer_id(a.get("url", ""))}

    driver = create_driver()
    added = 0
    updated = 0
    errors = 0

    def process_one(url, offer_id):
        """Получить HTML через браузер, сохранить, распарсить, скачать фото, вернуть True при успехе."""
        html = fetch_html_with_browser(driver, url)
        if not html:
            return False
        if is_captcha_page(html):
            return False
        html_path = os.path.join(STATIC_4_DIR, offer_id + ".html")
        with open(html_path, "w", encoding="utf-8", errors="replace") as f:
            f.write(html)
        parsed = parse_offer_page(html, url)
        image_urls = parsed.pop("image_urls", [])
        local_photos = download_images(offer_id, image_urls, STATIC_4_DIR)
        record = build_apartment_record(offer_id, url, parsed, local_photos)
        if offer_id in by_id:
            by_id[offer_id].update(record)
        else:
            apartments.append(record)
            by_id[offer_id] = record
        return True

    try:
        for i, url in enumerate(unique_urls):
            offer_id = extract_offer_id(url)
            if not offer_id:
                continue
            print(f"[{i+1}/{len(unique_urls)}] {offer_id} ... ", end="", flush=True)

            try:
                existed_before = offer_id in by_id
                ok = process_one(url, offer_id)
            except (InvalidSessionIdException, WebDriverException):
                print(f"браузер закрыт или сессия потеряна — сохраняю прогресс и перезапускаю Chrome...", flush=True)
                save_progress(apartments)
                try:
                    driver.quit()
                except Exception:
                    pass
                driver = create_driver()
                try:
                    ok = process_one(url, offer_id)
                except Exception as e2:
                    print(f"повтор не удался: {e2}", flush=True)
                    errors += 1
                    continue
                if ok:
                    if existed_before:
                        updated += 1
                    else:
                        added += 1
                    n = len(by_id[offer_id].get("photos") or [])
                    print(f"HTML + {n} фото (после перезапуска)", flush=True)
                else:
                    errors += 1
                save_progress(apartments)
                time.sleep(0.4)
                continue
            except Exception as e:
                print(f"ошибка: {e}", flush=True)
                errors += 1
                continue

            if not ok:
                print("не получен HTML (капча или ошибка)", flush=True)
                errors += 1
            else:
                if existed_before:
                    updated += 1
                else:
                    added += 1
                n = len(by_id[offer_id].get("photos") or [])
                print(f"HTML + {n} фото", flush=True)
            save_progress(apartments)
            time.sleep(0.4)
    finally:
        try:
            driver.quit()
        except Exception:
            pass

    # Финальное сохранение уже в цикле после каждой квартиры; перезаписываем на всякий случай
    save_progress(apartments)

    print(f"\nГотово. Добавлено: {added}, обновлено: {updated}, ошибок: {errors}.")
    print("Запустите: python scripts/create_map_cian.py")


if __name__ == "__main__":
    main()
