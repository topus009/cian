# -*- coding: utf-8 -*-
"""
Скачивание объявлений Авито через Chrome (Selenium) — как fetch_cian_offers_selenium.py.

Прямые HTTP-запросы часто дают 429; в браузере сессия и cookies как у пользователя.

  pip install selenium requests beautifulsoup4
  python scripts/fetch_avito_offers_selenium.py
  python scripts/fetch_avito_offers_selenium.py --resume
  python scripts/fetch_avito_offers_selenium.py --no-images
  python scripts/fetch_avito_offers_selenium.py --workers 3   # 3 Chrome параллельно (капчу — только в 1 воркере)

Ссылки: data/urls_avito.txt → data/apartments_avito.json (+ опционально HTML в data/avito_html/)

Парсинг: avito_offer_parse.py. После: python scripts/create_map_cian.py
"""
from __future__ import annotations

import argparse
import multiprocessing
import os
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)

try:
    import requests
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import InvalidSessionIdException, WebDriverException
except ImportError:
    print("Установите: pip install selenium requests beautifulsoup4")
    sys.exit(1)

from avito_offer_parse import (
    AVITO_DATA,
    HEADERS,
    OUT_JSON,
    ROOT,
    URLS_PATH,
    atomic_write_json,
    avito_item_id,
    collect_image_urls,
    load_by_id_from_json,
    parse_avito_html,
    rebuild_ordered,
)
from bs4 import BeautifulSoup

AVITO_HTML_DIR = os.path.join(ROOT, "data", "avito_html")


def load_urls() -> list[str]:
    if not os.path.isfile(URLS_PATH):
        return []
    out = []
    with open(URLS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("http"):
                out.append(line)
    return out


def create_driver(headless: bool = False):
    """Chrome. headless=new — без окон (удобно при нескольких воркерах)."""
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    opts.add_argument("--window-size=1400,950")
    opts.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
    if not headless:
        x, y = _worker_window_offset()
        opts.add_argument(f"--window-position={x},{y}")
    try:
        driver = webdriver.Chrome(options=opts)
    except Exception as e:
        raise RuntimeError(f"Не удалось запустить Chrome: {e}") from e
    try:
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});",
            },
        )
    except Exception:
        pass
    return driver


def _worker_window_offset() -> tuple[int, int]:
    """Слегка сдвигаем окна, если несколько процессов (видимый режим)."""
    wid = multiprocessing.current_process().name
    if wid.startswith("ForkPoolWorker") or wid.startswith("SpawnPoolWorker"):
        try:
            n = int(wid.rsplit("-", 1)[-1])
        except ValueError:
            n = 0
        return (40 + (n % 4) * 80, 40 + (n % 3) * 60)
    return (0, 0)


def is_likely_offer_page(html: str) -> bool:
    """Достаточно признаков реальной карточки (вёрстка Авито меняется)."""
    if not html or len(html) < 1500:
        return False
    has_title = 'data-marker="item-view/title-info"' in html
    has_price = (
        'data-marker="item-view/item-price"' in html
        or 'data-marker="item-view/item-price-container"' in html
        or ('itemprop="price"' in html and 'content="' in html)
    )
    if has_title and has_price:
        return True
    # Редкий вариант: заголовок + блок карты объявления
    if has_title and 'data-marker="item-map-wrapper"' in html:
        return True
    return False


def is_antibot_or_rate_limit(html: str) -> bool:
    """Не считать «короткий HTML» автоматически ботом — у headless сначала бывает оболочка."""
    if not html:
        return True
    low = html.lower()
    if "too many requests" in low or " 429" in low or "http 429" in low:
        return True
    if "доступ ограничен" in low or "временно ограничен" in low:
        return True
    if "подозрительная активность" in low:
        return True
    if "smartcaptcha" in low:
        return True
    # Явная заглушка без контента карточки
    if len(html) < 2500 and ("подтвердите" in low or "робот" in low):
        return True
    return False


def wait_for_offer(driver, timeout_sec: float = 90) -> bool:
    """Одно ожидание: появился заголовок или блок цены."""
    combined = ", ".join(
        [
            'h1[data-marker="item-view/title-info"]',
            '[data-marker="item-view/item-price"]',
            '[data-marker="item-view/item-price-container"]',
        ]
    )
    try:
        WebDriverWait(driver, timeout_sec).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, combined))
        )
        return True
    except Exception:
        return False


def fetch_page_html(
    driver, url: str, interactive: bool = True, headless: bool = False
) -> str | None:
    driver.get(url)
    time.sleep(3.5 if headless else 1)
    try:
        driver.execute_script("window.scrollTo(0, 400);")
    except Exception:
        pass

    wait_sec = 120 if headless else 90
    if wait_for_offer(driver, wait_sec):
        time.sleep(0.8 if headless else 0.35)
        html = driver.page_source
        if is_likely_offer_page(html):
            return html

    html = driver.page_source
    if is_likely_offer_page(html):
        if not is_antibot_or_rate_limit(html):
            return html
        # разметка карточки есть — не отсекаем из‑за ложного antibot
        if "item-view/title-info" in html and "item-view/item-price" in html:
            return html

    if interactive:
        print("    Не вижу карточку объявления (антибот / 429 / капча).")
        print("    В открытом Chrome: обновите страницу, пройдите проверку, при необходимости залогиньтесь.")
        input("    Нажмите Enter, когда на странице видно объявление… ")
        time.sleep(0.8)
        if wait_for_offer(driver, 45):
            time.sleep(0.3)
        html = driver.page_source
        if is_likely_offer_page(html):
            return html
        print("    Всё ещё нет разметки объявления — пропуск URL.")
    return None


def requests_session_from_driver(driver) -> requests.Session:
    """Cookies из браузера — для скачивания картинок с img.avito.st."""
    s = requests.Session()
    s.headers.update(HEADERS)
    for c in driver.get_cookies():
        domain = c.get("domain") or ""
        path = c.get("path") or "/"
        try:
            s.cookies.set(c["name"], c["value"], domain=domain, path=path)
        except Exception:
            s.cookies.set(c["name"], c["value"])
    return s


def download_image(session: requests.Session, url: str, dest: str) -> bool:
    try:
        r = session.get(url, timeout=120, allow_redirects=True)
        r.raise_for_status()
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            f.write(r.content)
        return True
    except Exception:
        return False


def process_one(
    driver,
    url: str,
    aid: str,
    no_images: bool,
    save_html: bool,
    interactive: bool = True,
    headless: bool = False,
) -> dict | None:
    html = fetch_page_html(
        driver, url, interactive=interactive, headless=headless
    )
    if not html:
        return None
    # Пробуем парсер даже при слабых эвристиках (часть полей может быть)
    if not is_likely_offer_page(html):
        rec_try = parse_avito_html(html, url)
        if not rec_try or not rec_try.get("title") or rec_try["title"].startswith(
            "Объявление "
        ):
            return None
    else:
        rec_try = None

    if not is_likely_offer_page(html) and rec_try:
        rec = rec_try
        soup = BeautifulSoup(html, "html.parser")
        remote = collect_image_urls(soup, html)
        rec["photos"] = []
        rec["img_src"] = ""
        if not no_images and aid and remote:
            img_session = requests_session_from_driver(driver)
            folder = os.path.join(AVITO_DATA, f"{aid}_files")
            for j, purl in enumerate(remote[:40]):
                ext = ".webp" if ".webp" in purl.lower() else ".jpg"
                dest = os.path.join(folder, f"photo_{j+1}{ext}")
                if download_image(img_session, purl, dest):
                    rel = os.path.relpath(dest, ROOT).replace("\\", "/")
                    rec["photos"].append(rel)
                time.sleep(0.12)
            if rec["photos"]:
                rec["img_src"] = rec["photos"][0]
        else:
            rec["photos"] = remote[:40]
            rec["img_src"] = remote[0] if remote else ""
        if save_html:
            os.makedirs(AVITO_HTML_DIR, exist_ok=True)
            hp = os.path.join(AVITO_HTML_DIR, f"{aid}.html")
            with open(hp, "w", encoding="utf-8", errors="replace") as f:
                f.write(html)
        return rec

    if save_html:
        os.makedirs(AVITO_HTML_DIR, exist_ok=True)
        hp = os.path.join(AVITO_HTML_DIR, f"{aid}.html")
        with open(hp, "w", encoding="utf-8", errors="replace") as f:
            f.write(html)

    rec = parse_avito_html(html, url)
    if not rec:
        return None

    soup = BeautifulSoup(html, "html.parser")
    remote = collect_image_urls(soup, html)
    rec["photos"] = []
    rec["img_src"] = ""

    if not no_images and aid and remote:
        img_session = requests_session_from_driver(driver)
        folder = os.path.join(AVITO_DATA, f"{aid}_files")
        for j, purl in enumerate(remote[:40]):
            ext = ".webp" if ".webp" in purl.lower() else ".jpg"
            dest = os.path.join(folder, f"photo_{j+1}{ext}")
            if download_image(img_session, purl, dest):
                rel = os.path.relpath(dest, ROOT).replace("\\", "/")
                rec["photos"].append(rel)
            time.sleep(0.12)
        if rec["photos"]:
            rec["img_src"] = rec["photos"][0]
    else:
        rec["photos"] = remote[:40]
        rec["img_src"] = remote[0] if remote else ""

    return rec


def split_into_n_chunks(lst: list[str], n: int) -> list[list[str]]:
    if not lst:
        return []
    n = max(1, min(n, len(lst)))
    q, r = divmod(len(lst), n)
    out: list[list[str]] = []
    i = 0
    for j in range(n):
        sz = q + (1 if j < r else 0)
        out.append(lst[i : i + sz])
        i += sz
    return out


def run_single_worker(urls, by_id, args, save_html: bool) -> dict[str, dict]:
    """Один процесс: можно жать Enter при капче."""
    driver = None
    try:
        driver = create_driver(headless=args.headless)
    except RuntimeError as e:
        print(e)
        return by_id
    interactive = not args.no_interactive
    try:
        for i, url in enumerate(urls):
            aid = avito_item_id(url)
            if not aid:
                print(
                    f"[{i+1}/{len(urls)}] пропуск (нет id в URL): {url[:60]}…",
                    flush=True,
                )
                continue
            print(f"[{i+1}/{len(urls)}] {aid} …", flush=True)
            if args.resume and aid in by_id:
                print("  пропуск (уже есть)", flush=True)
                continue
            try:
                rec = process_one(
                    driver,
                    url,
                    aid,
                    args.no_images,
                    save_html,
                    interactive=interactive,
                    headless=args.headless,
                )
            except (InvalidSessionIdException, WebDriverException):
                print("  браузер закрыт — перезапуск Chrome…", flush=True)
                try:
                    driver.quit()
                except Exception:
                    pass
                try:
                    driver = create_driver(headless=args.headless)
                except RuntimeError as e:
                    print(e, flush=True)
                    break
                rec = process_one(
                    driver,
                    url,
                    aid,
                    args.no_images,
                    save_html,
                    interactive=interactive,
                    headless=args.headless,
                )
            except Exception as e:
                print(f"  ошибка: {e}", flush=True)
                rec = None
            if not rec:
                print("  не получилось", flush=True)
                time.sleep(args.delay)
                continue
            by_id[aid] = rec
            ordered = rebuild_ordered(urls, by_id)
            atomic_write_json(OUT_JSON, ordered)
            print(f"  OK — в файле {len(ordered)} шт.", flush=True)
            time.sleep(args.delay)
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass
        ordered = rebuild_ordered(urls, by_id)
        if ordered:
            atomic_write_json(OUT_JSON, ordered)
    return by_id


def main():
    ap = argparse.ArgumentParser(description="Авито через Selenium + Chrome")
    ap.add_argument("--resume", action="store_true", help="Пропускать id из текущего apartments_avito.json")
    ap.add_argument("--no-images", action="store_true", help="Только поля + URL фото, без загрузки файлов")
    ap.add_argument("--no-save-html", action="store_true", help="Не сохранять data/avito_html/<id>.html")
    ap.add_argument("--delay", type=float, default=0.6, help="Пауза после каждого объявления на воркер, сек")
    ap.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Число параллельных Chrome (процессы). >1 — без input() при капче; лучше --headless",
    )
    ap.add_argument(
        "--headless",
        action="store_true",
        help="Chrome без окна (меньше нагрузка на GPU/RAM при нескольких воркерах)",
    )
    ap.add_argument(
        "--no-interactive",
        action="store_true",
        help="Не ждать Enter при проблемной странице (только один воркер)",
    )
    args = ap.parse_args()

    urls = load_urls()
    if not urls:
        print(f"Нет URL в {URLS_PATH}")
        return 1

    by_id = load_by_id_from_json(OUT_JSON)
    if by_id:
        print(
            f"В JSON уже {len(by_id)} объявлений — при неудачной загрузке записи не теряются."
        )
    if args.resume:
        print("--resume: качаем только id, которых ещё нет в файле.")

    os.makedirs(AVITO_DATA, exist_ok=True)
    save_html = not args.no_save_html

    pending = [
        u
        for u in urls
        if (aid := avito_item_id(u)) and (not args.resume or aid not in by_id)
    ]
    if not pending:
        if args.resume:
            print("Нечего качать: все id уже в JSON.")
        ordered = rebuild_ordered(urls, by_id)
        if ordered:
            atomic_write_json(OUT_JSON, ordered)
        print(f"\nГотово: {OUT_JSON} — {len(ordered)} из {len(urls)} URL")
        try:
            import subprocess

            subprocess.run(
                [sys.executable, os.path.join(SCRIPT_DIR, "create_map_cian.py")],
                cwd=ROOT,
                check=False,
            )
        except Exception:
            print("Запустите: python scripts/create_map_cian.py")
        return 0

    n_workers = max(1, args.workers)
    if len(pending) < n_workers:
        n_workers = max(1, len(pending))
        if n_workers != args.workers:
            print(f"Воркеров: {n_workers} (по числу URL в очереди)")

    if n_workers == 1:
        run_single_worker(urls, by_id, args, save_html)
    else:
        from avito_mp_worker import worker_entry as mp_worker_entry

        print(
            f"Параллельно: {n_workers} процессов Chrome. "
            "Капча/ручной ввод отключены — неудачные страницы пропускаются.",
            flush=True,
        )
        if args.headless:
            print(
                "ВНИМАНИЕ: headless + несколько воркеров у Авито часто даёт 0 карточек. "
                "Надёжнее: --workers 1 без --headless (или докачка с --resume).",
                flush=True,
            )
        else:
            print("Докачка при пропусках: --workers 1", flush=True)
        chunks = split_into_n_chunks(pending, n_workers)
        interactive = False
        payloads = [
            (
                idx,
                chunk,
                args.no_images,
                save_html,
                args.delay,
                interactive,
                args.headless,
            )
            for idx, chunk in enumerate(chunks)
            if chunk
        ]
        ctx = multiprocessing.get_context("spawn")
        with ctx.Pool(processes=len(payloads)) as pool:
            batches = pool.map(mp_worker_entry, payloads)
        for batch in batches:
            for rec in batch:
                aid = rec.get("avito_id")
                if aid:
                    by_id[str(aid)] = rec
        ordered = rebuild_ordered(urls, by_id)
        if ordered:
            atomic_write_json(OUT_JSON, ordered)

    print(f"\nГотово: {OUT_JSON} — {len(rebuild_ordered(urls, by_id))} из {len(urls)} URL")
    try:
        import subprocess

        subprocess.run(
            [sys.executable, os.path.join(SCRIPT_DIR, "create_map_cian.py")],
            cwd=ROOT,
            check=False,
        )
    except Exception:
        print("Запустите: python scripts/create_map_cian.py")
    return 0


if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())
