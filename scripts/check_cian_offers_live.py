# -*- coding: utf-8 -*-
"""
Проверка объявлений Циан по живым URL из data/apartments.json.

Для каждой квартиры:
  - GET по ссылке; если ответ 404 — объявление больше не существует.
  - Если 200 — в HTML ищется блок с data-name="OfferUnpublished"
    («Объявление снято с публикации»).

Возвращает список ID (число из URL .../sale/flat/<ID>) с причиной.

Запуск из корня проекта:
  python scripts/check_cian_offers_live.py
  python scripts/check_cian_offers_live.py --json
  python scripts/check_cian_offers_live.py --delay 1.5
  python scripts/check_cian_offers_live.py --no-progress   # без строки прогресса

Зависимости: pip install requests beautifulsoup4

Примечание: при блокировке/капче Циан может вернуть не 404 и не нормальную страницу —
тогда результат может быть неточным; при необходимости используйте Selenium.
"""
import argparse
import json
import os
import re
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
JSON_PATH = os.path.join(ROOT, "data", "apartments.json")

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Установите: pip install requests beautifulsoup4", file=sys.stderr)
    sys.exit(1)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}


def extract_offer_id(url):
    m = re.search(r"sale/flat/(\d+)", url or "")
    return m.group(1) if m else None


def has_offer_unpublished(html):
    if not html:
        return False
    soup = BeautifulSoup(html, "html.parser")
    el = soup.find(attrs={"data-name": "OfferUnpublished"})
    return el is not None


def progress_bar(done, total, width=28):
    """Полоска как при установке: # — сделано, . — осталось."""
    if total <= 0:
        return "[" + " " * width + "]"
    filled = int(round(width * done / total))
    filled = min(max(filled, 0), width)
    return "[" + "#" * filled + "." * (width - filled) + "]"


def reason_short(reason):
    if reason == "ok":
        return "OK"
    if reason == "not_found_404":
        return "404 нет объявления"
    if reason == "unpublished":
        return "снято с публикации"
    if reason == "bad_url":
        return "неверный URL"
    if reason.startswith("http_"):
        return "HTTP " + reason.replace("http_", "")
    if reason.startswith("request_error"):
        return "сеть/таймаут"
    return reason[:40]


def check_url(session, url, timeout):
    """
    Возвращает (offer_id, reason, http_status).
    reason: 'ok' | 'not_found_404' | 'unpublished' | 'http_error' | 'request_error'
    """
    oid = extract_offer_id(url)
    if not oid:
        return None, "bad_url", None
    try:
        r = session.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
    except requests.RequestException as e:
        return oid, f"request_error:{e!s}", None

    status = r.status_code
    if status == 404:
        return oid, "not_found_404", status
    if status != 200:
        return oid, f"http_{status}", status

    text = r.text or ""
    if has_offer_unpublished(text):
        return oid, "unpublished", status
    return oid, "ok", status


def main():
    parser = argparse.ArgumentParser(description="Проверка объявлений Циан на снятие/404")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Вывести результат в JSON (stdout)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.4,
        metavar="SEC",
        help="Пауза между запросами, сек (по умолчанию 0.4)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=25.0,
        help="Таймаут HTTP, сек",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Не выводить строку прогресса",
    )
    args = parser.parse_args()

    if not os.path.isfile(JSON_PATH):
        print(f"Нет файла: {JSON_PATH}", file=sys.stderr)
        return 1

    with open(JSON_PATH, encoding="utf-8") as f:
        apartments = json.load(f)

    seen_urls = set()
    urls = []
    for apt in apartments:
        u = (apt.get("url") or "").strip()
        if not u or u in seen_urls:
            continue
        seen_urls.add(u)
        urls.append(u)

    session = requests.Session()
    problems = []
    ok_count = 0
    error_count = 0
    total = len(urls)
    # При --json прогресс в stderr, чтобы stdout остался чистым JSON
    prog_out = sys.stderr if args.json else sys.stdout

    if not args.no_progress and total > 0:
        print("", file=prog_out)
        print("Проверка объявлений Циан (живой запрос к каждому URL)", file=prog_out)
        print("Всего уникальных квартир: %d" % total, file=prog_out)
        print("—" * 60, file=prog_out)

    for i, url in enumerate(urls):
        oid, reason, status = check_url(session, url, args.timeout)
        if oid is None:
            if not args.no_progress and total > 0:
                cur = i + 1
                bar = progress_bar(cur, total)
                line = "\r%s  %d / %d   (пропуск: нет ID в URL)" % (bar, cur, total)
                print(line, end="", flush=True, file=prog_out)
            if i + 1 < len(urls) and args.delay > 0:
                time.sleep(args.delay)
            continue
        if reason == "ok":
            ok_count += 1
        elif reason in ("not_found_404", "unpublished"):
            problems.append(
                {
                    "id": oid,
                    "url": url,
                    "reason": reason,
                    "http_status": status,
                }
            )
        else:
            error_count += 1
            problems.append(
                {
                    "id": oid,
                    "url": url,
                    "reason": reason,
                    "http_status": status,
                }
            )

        cur = i + 1
        if not args.no_progress and total > 0:
            bar = progress_bar(cur, total)
            st = reason_short(reason)
            line = "\r%s  %d / %d   ID %s   %s" % (bar, cur, total, oid, st)
            print(line, end="", flush=True, file=prog_out)

        if i + 1 < len(urls) and args.delay > 0:
            time.sleep(args.delay)

    if not args.no_progress and total > 0:
        print(file=prog_out)  # перевод строки после \r
        print("—" * 60, file=prog_out)
        print("Запросы завершены.", file=prog_out)
        print("", file=prog_out)

    # Отдельно: только «снято» и «404», без сетевых сбоев — для удобства
    dead_or_unpublished = [p for p in problems if p["reason"] in ("not_found_404", "unpublished")]

    if args.json:
        out = {
            "not_found_404_or_unpublished": dead_or_unpublished,
            "ids_dead_or_unpublished": [p["id"] for p in dead_or_unpublished],
            "all_issues_including_errors": problems,
            "summary": {
                "total_checked": len(urls),
                "ok": ok_count,
                "not_found_404": sum(1 for p in dead_or_unpublished if p["reason"] == "not_found_404"),
                "unpublished": sum(1 for p in dead_or_unpublished if p["reason"] == "unpublished"),
                "other_errors": error_count,
            },
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(f"Проверено URL: {len(urls)}")
        print(f"Активные (OK): {ok_count}")
        print()
        if dead_or_unpublished:
            print("ID с 404 или снято с публикации (OfferUnpublished):")
            for p in dead_or_unpublished:
                label = "404" if p["reason"] == "not_found_404" else "снято"
                print(f"  {p['id']}  ({label})  {p['url']}")
        else:
            print("Нет объявлений с 404 или OfferUnpublished.")
        if problems and len(problems) > len(dead_or_unpublished):
            print()
            print("Прочие проблемы (HTTP не 200/200+ошибка запроса):")
            for p in problems:
                if p["reason"] in ("not_found_404", "unpublished"):
                    continue
                print(f"  {p['id']}  {p['reason']}  {p['url']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
