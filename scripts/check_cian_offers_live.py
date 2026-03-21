# -*- coding: utf-8 -*-
"""
Проверка объявлений Циан по живым URL из data/apartments.json.

Для каждой квартиры один GET, затем до трёх проверок по HTML:

  1. HTTP 404 — объявление удалено.
  2. Блок data-name="OfferUnpublished" — снято с публикации.
  3. Блоки data-name="OfferSummaryInfoItem": строка «Газоснабжение» и значение
     (например «Центральное») — есть газ; «Нет», «Отсутствует» и т.п. — не считаем.

Возвращает списки ID: проблемные (404/снято) и с газом.

Запуск из корня проекта:
  python scripts/check_cian_offers_live.py
  python scripts/check_cian_offers_live.py --json
  python scripts/check_cian_offers_live.py --delay 1.5
  python scripts/check_cian_offers_live.py --no-progress
  python scripts/check_cian_offers_live.py --skip-gas   # только 404 и снятие

Зависимости: pip install requests beautifulsoup4

Примечание: при блокировке/капче Циан результат может быть неточным; при необходимости — Selenium.
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

# Значения газоснабжения, при которых газа нет (нижний регистр, подстрока)
GAS_NEGATIVE_VALUES = (
    "нет",
    "отсутств",
    "не указано",
    "не указан",
    "без газа",
    "нет газа",
    "—",
    "-",
    "н/д",
)


def extract_offer_id(url):
    m = re.search(r"sale/flat/(\d+)", url or "")
    return m.group(1) if m else None


def has_offer_unpublished(html):
    if not html:
        return False
    soup = BeautifulSoup(html, "html.parser")
    return soup.find(attrs={"data-name": "OfferUnpublished"}) is not None


def parse_gas_supply(html):
    """
    Ищет OfferSummaryInfoItem с подписью «Газоснабжение» (data-name как на Циан).
    Возвращает (has_gas: bool, value_text: str|None).
    """
    if not html:
        return False, None
    soup = BeautifulSoup(html, "html.parser")
    for item in soup.find_all(attrs={"data-name": "OfferSummaryInfoItem"}):
        ps = item.find_all("p")
        if len(ps) < 2:
            continue
        label = (ps[0].get_text() or "").strip()
        value = (ps[1].get_text() or "").strip()
        if not label or "газоснабж" not in label.lower():
            continue
        if not value:
            return False, None
        vlow = value.lower()
        if any(neg in vlow for neg in GAS_NEGATIVE_VALUES):
            return False, value
        return True, value
    return False, None


def progress_bar(done, total, width=28):
    if total <= 0:
        return "[" + " " * width + "]"
    filled = int(round(width * done / total))
    filled = min(max(filled, 0), width)
    return "[" + "#" * filled + "." * (width - filled) + "]"


def reason_short(reason, has_gas=None, gas_value=None):
    if reason == "ok":
        if has_gas:
            gv = (gas_value or "газ")[:18]
            return "OK, газ: " + gv
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


def fetch_and_analyze(session, url, timeout, check_gas):
    """
    Один запрос. Возвращает:
      (offer_id, reason, http_status, has_gas, gas_value)
    has_gas / gas_value осмысленны только при reason == 'ok' и check_gas True.
    """
    oid = extract_offer_id(url)
    if not oid:
        return None, "bad_url", None, False, None
    try:
        r = session.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
    except requests.RequestException as e:
        return oid, "request_error:%s" % (e,), None, False, None

    status = r.status_code
    if status == 404:
        return oid, "not_found_404", status, False, None
    if status != 200:
        return oid, "http_%s" % status, status, False, None

    text = r.text or ""
    if has_offer_unpublished(text):
        return oid, "unpublished", status, False, None

    has_gas = False
    gas_value = None
    if check_gas:
        has_gas, gas_value = parse_gas_supply(text)

    return oid, "ok", status, has_gas, gas_value


def main():
    parser = argparse.ArgumentParser(
        description="Проверка Циан: 404, снятие с публикации, газоснабжение (OfferSummaryInfoItem)"
    )
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
    parser.add_argument(
        "--skip-gas",
        action="store_true",
        help="Не искать газ (только 404 и OfferUnpublished)",
    )
    args = parser.parse_args()
    check_gas = not args.skip_gas

    if not os.path.isfile(JSON_PATH):
        print("Нет файла: %s" % JSON_PATH, file=sys.stderr)
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
    with_gas_list = []
    ok_count = 0
    error_count = 0
    total = len(urls)
    prog_out = sys.stderr if args.json else sys.stdout

    if not args.no_progress and total > 0:
        print("", file=prog_out)
        print("Проверка объявлений Циан (404 / снято / газ)", file=prog_out)
        print("Всего уникальных квартир: %d" % total, file=prog_out)
        if check_gas:
            print("Проверка газа: блоки data-name=\"OfferSummaryInfoItem\", подпись «Газоснабжение»", file=prog_out)
        else:
            print("Проверка газа отключена (--skip-gas)", file=prog_out)
        print("—" * 60, file=prog_out)

    for i, url in enumerate(urls):
        oid, reason, status, has_gas, gas_value = fetch_and_analyze(
            session, url, args.timeout, check_gas
        )
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
            if check_gas and has_gas:
                with_gas_list.append(
                    {
                        "id": oid,
                        "url": url,
                        "gas_supply": gas_value or "",
                        "http_status": status,
                    }
                )
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
            st = reason_short(
                reason,
                has_gas=(reason == "ok" and check_gas and has_gas),
                gas_value=gas_value,
            )
            line = "\r%s  %d / %d   ID %s   %s" % (bar, cur, total, oid, st)
            print(line, end="", flush=True, file=prog_out)

        if i + 1 < len(urls) and args.delay > 0:
            time.sleep(args.delay)

    if not args.no_progress and total > 0:
        print(file=prog_out)
        print("—" * 60, file=prog_out)
        print("Запросы завершены.", file=prog_out)
        print("", file=prog_out)

    dead_or_unpublished = [p for p in problems if p["reason"] in ("not_found_404", "unpublished")]

    if args.json:
        out = {
            "not_found_404_or_unpublished": dead_or_unpublished,
            "ids_dead_or_unpublished": [p["id"] for p in dead_or_unpublished],
            "with_gas_supply": with_gas_list,
            "ids_with_gas": [p["id"] for p in with_gas_list],
            "all_issues_including_errors": problems,
            "summary": {
                "total_checked": len(urls),
                "ok": ok_count,
                "not_found_404": sum(
                    1 for p in dead_or_unpublished if p["reason"] == "not_found_404"
                ),
                "unpublished": sum(
                    1 for p in dead_or_unpublished if p["reason"] == "unpublished"
                ),
                "with_gas": len(with_gas_list),
                "other_errors": error_count,
                "gas_check_enabled": check_gas,
            },
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print("Проверено URL: %d" % len(urls))
        print("Активные (OK): %d" % ok_count)
        if check_gas:
            print("С газоснабжением (по странице): %d" % len(with_gas_list))
        print()
        if dead_or_unpublished:
            print("ID с 404 или снято с публикации (OfferUnpublished):")
            for p in dead_or_unpublished:
                label = "404" if p["reason"] == "not_found_404" else "снято"
                print("  %s  (%s)  %s" % (p["id"], label, p["url"]))
        else:
            print("Нет объявлений с 404 или OfferUnpublished.")
        if check_gas and with_gas_list:
            print()
            print("ID с газоснабжением (OfferSummaryInfoItem → Газоснабжение):")
            for p in with_gas_list:
                gv = p.get("gas_supply") or "—"
                print("  %s  (%s)  %s" % (p["id"], gv, p["url"]))
        if problems and len(problems) > len(dead_or_unpublished):
            print()
            print("Прочие проблемы (HTTP не 200 / ошибка запроса):")
            for p in problems:
                if p["reason"] in ("not_found_404", "unpublished"):
                    continue
                print("  %s  %s  %s" % (p["id"], p["reason"], p["url"]))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
