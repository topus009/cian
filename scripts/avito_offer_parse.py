# -*- coding: utf-8 -*-
"""
Общие константы и парсинг HTML объявления Авито (для fetch_avito_offers_selenium.py).

Вёрстка: h1[data-marker=item-view/title-info], item-view/item-params, карта, фото, описание.
"""
from __future__ import annotations

import json
import os
import re
from html import unescape
from urllib.parse import urlparse

from bs4 import BeautifulSoup, NavigableString

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
URLS_PATH = os.path.join(ROOT, "data", "urls_avito.txt")
OUT_JSON = os.path.join(ROOT, "data", "apartments_avito.json")
AVITO_DATA = os.path.join(ROOT, "data", "avito")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}


def atomic_write_json(path: str, data: object) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def load_by_id_from_json(path: str) -> dict[str, dict]:
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            arr = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
    out: dict[str, dict] = {}
    for r in arr:
        aid = r.get("avito_id")
        if aid:
            out[str(aid)] = r
    return out


def avito_item_id(url: str) -> str | None:
    path = urlparse(url).path.rstrip("/")
    m = re.search(r"_(\d+)$", path)
    return m.group(1) if m else None


def rebuild_ordered(urls: list[str], by_id: dict[str, dict]) -> list[dict]:
    ordered: list[dict] = []
    for u in urls:
        aid = avito_item_id(u)
        if aid and aid in by_id:
            ordered.append(by_id[aid])
    return ordered


def norm_space(s: str) -> str:
    if not s:
        return ""
    t = unescape(s).replace("\xa0", " ").replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", t).strip()


def li_label_value(li) -> tuple[str, str] | None:
    span = li.find("span", recursive=False)
    if not span:
        return None
    label = norm_space(span.get_text(" ", strip=True)).rstrip(":").strip()
    parts = []
    for sib in span.next_siblings:
        if isinstance(sib, NavigableString):
            t = str(sib).strip()
            if t:
                parts.append(t)
        elif getattr(sib, "name", None):
            parts.append(sib.get_text(" ", strip=True))
    value = norm_space(" ".join(parts))
    return (label, value) if label else None


def parse_item_params_blocks(soup: BeautifulSoup) -> tuple[dict, dict]:
    blocks = soup.select('[data-marker="item-view/item-params"]')
    flat_d: dict[str, str] = {}
    house_d: dict[str, str] = {}
    for block in blocks:
        h2 = block.find("h2")
        h2t = norm_space(h2.get_text(" ", strip=True)) if h2 else ""
        ul = block.find("ul")
        if not ul:
            continue
        target = house_d if "дом" in h2t.lower() else flat_d
        for li in ul.find_all("li", recursive=False):
            pair = li_label_value(li)
            if not pair:
                continue
            lab, val = pair
            target[lab] = val
    return flat_d, house_d


def parse_floor(s: str) -> str | None:
    s = norm_space(s)
    m = re.search(r"(\d+)\s*из\s*(\d+)", s, re.I)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    m = re.search(r"(\d+)\s*/\s*(\d+)", s)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    return None


def parse_area_m2(s: str) -> str | None:
    m = re.search(r"([\d,\.]+)\s*м", s.replace(",", "."))
    if m:
        v = m.group(1).replace(",", ".")
        try:
            x = float(v)
            return str(int(x)) if x == int(x) else str(round(x, 1))
        except ValueError:
            return v
    return None


def _urls_from_embedded_imageurls_json(page_html: str) -> list[str]:
    """
    В разметке объявления Авито в <script> лежит JSON с полем urls / imageUrls:
    для каждого фото — несколько размеров. Берём 1280x960 (макс. из типичного набора),
    иначе объявление качается с превью 75×55 / 150×110 — нечитаемо.

    В HTML кавычки экранированы: \\\"1280x960\\\":\\\"https://...
    """
    if not page_html or "1280x960" not in page_html:
        return []
    # Экранированный JSON внутри строки JS
    pat_esc = r'\\"1280x960\\":\\"(https://.*?)(?=\\")'
    found = re.findall(pat_esc, page_html)
    if not found:
        # На случай неэкранированного варианта
        found = re.findall(
            r'"1280x960"\s*:\s*"(https://[^"]+)"', page_html
        )
    out: list[str] = []
    seen: set[str] = set()
    for u in found:
        u = u.replace("\\/", "/").strip()
        if u and u not in seen and "img.avito.st" in u:
            seen.add(u)
            out.append(u)
    return out


def _urls_from_extended_gallery(soup: BeautifulSoup) -> list[str]:
    """
    Полноэкранная галерея Авито: <img data-marker="extended-gallery/frame-img" src="…?cqp=…">
    Тот же класс URL, что и ключ 1280x960 во встроенном JSON (~1280×960), с подписью cqp.
    Появляется в DOM после открытия галереи; в сохранённом page_source Selenium иногда уже есть.
    """
    imgs = soup.select('[data-marker="extended-gallery/frame-img"][src]')
    if not imgs:
        return []

    def sort_key(i: int, img) -> tuple[int, int]:
        raw = img.get("data-image-id")
        try:
            return (int(raw), i)
        except (TypeError, ValueError):
            return (i, i)

    ranked = sorted(enumerate(imgs), key=lambda t: sort_key(t[0], t[1]))
    out: list[str] = []
    seen: set[str] = set()
    for _, img in ranked:
        src = (img.get("src") or "").strip()
        if not src or "img.avito.st" not in src or src in seen:
            continue
        seen.add(src)
        out.append(src)
    return out


def collect_image_urls(soup: BeautifulSoup, page_html: str = "") -> list[str]:
    """URL фото: JSON 1280×960 → extended-gallery/frame-img → превью в DOM."""
    from_json = _urls_from_embedded_imageurls_json(page_html)
    if from_json:
        return from_json

    from_gallery = _urls_from_extended_gallery(soup)
    if from_gallery:
        return from_gallery

    out: list[str] = []
    seen: set[str] = set()
    wrap = soup.select_one('[data-marker="image-preview/preview-wrapper"]')
    if not wrap:
        for img in soup.select('[data-marker="item-view/gallery"] img[src]'):
            src = (img.get("src") or "").strip()
            if not src or "avito" not in src:
                continue
            if src not in seen:
                seen.add(src)
                out.append(src)
        return out
    for li in wrap.select('li[data-marker="image-preview/item"]'):
        if li.get("data-type") == "video":
            continue
        img = li.find("img", src=True)
        if not img:
            continue
        src = (img.get("src") or "").strip()
        if not src or src in seen:
            continue
        seen.add(src)
        out.append(src)
    return out


def parse_avito_html(html: str, page_url: str) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")
    item_id = avito_item_id(page_url)
    if not item_id:
        return None

    h1 = soup.select_one('h1[data-marker="item-view/title-info"]')
    title = norm_space(h1.get_text(" ", strip=True)) if h1 else ""

    flat_p, house_p = parse_item_params_blocks(soup)
    total_area = None
    for key in ("Общая площадь",):
        if key in flat_p:
            total_area = parse_area_m2(flat_p[key])
            break
    if not total_area and title:
        m = re.search(r"(\d+(?:[.,]\d+)?)\s*м", title)
        if m:
            total_area = parse_area_m2(m.group(0))

    floor = None
    if "Этаж" in flat_p:
        floor = parse_floor(flat_p["Этаж"])

    build_year = None
    if "Год постройки" in house_p:
        my = re.search(r"(19\d{2}|20\d{2})", house_p["Год постройки"])
        if my:
            build_year = int(my.group(1))

    price_value = None
    price_human = ""
    meta_price = soup.select_one('meta[itemprop="price"][content]')
    if meta_price and meta_price.get("content"):
        try:
            price_value = int(meta_price["content"])
        except ValueError:
            pass
    price_el = soup.select_one('[data-marker="item-view/item-price"]')
    if price_el:
        price_human = norm_space(price_el.get_text(" ", strip=True))
    if price_value is None and price_human:
        digits = re.sub(r"\D", "", price_human)
        if digits:
            price_value = int(digits)

    price_per_sqm = None
    for p in soup.find_all("p"):
        t = norm_space(p.get_text(" ", strip=True))
        if "за" in t.lower() and "м²" in t and "₽" in t:
            m = re.search(r"([\d\s]+)\s*₽", t)
            if m:
                price_per_sqm = int(re.sub(r"\s", "", m.group(1)))
            break

    lat = lon = None
    map_wrap = soup.select_one('[data-marker="item-map-wrapper"]')
    if map_wrap:
        try:
            lat = float(map_wrap.get("data-map-lat", "").replace(",", "."))
            lon = float(map_wrap.get("data-map-lon", "").replace(",", "."))
        except (TypeError, ValueError):
            lat = lon = None

    address = ""
    place = soup.find(attrs={"itemtype": re.compile(r"schema\.org/Place", re.I)})
    if place:
        addr_el = place.find(attrs={"itemprop": "address"})
        if addr_el:
            span = addr_el.find("span")
            address = norm_space((span or addr_el).get_text(" ", strip=True))

    metro_lines: list[str] = []
    if place:
        for row in place.select("span._22d8cf68e753a9b9"):
            line = norm_space(row.get_text(" ", strip=True))
            if line and len(line) > 3:
                metro_lines.append(line)
    if not metro_lines:
        loc = place.get_text(" ", strip=True) if place else ""
        if loc and address:
            extra = loc.replace(address, "", 1).strip()
            if extra:
                metro_lines = [extra[:200]]

    desc_el = soup.select_one('[data-marker="item-view/item-description"]')
    description = norm_space(desc_el.get_text("\n", strip=True)) if desc_el else ""

    price_display = price_human
    if not price_display and price_value:
        price_display = f"{price_value:,}".replace(",", " ") + " ₽"

    return {
        "source": "avito",
        "url": page_url.split("?")[0],
        "title": title or f"Объявление {item_id}",
        "price": price_display,
        "price_value": price_value,
        "price_per_sqm": price_per_sqm,
        "address": address,
        "metro": metro_lines,
        "phone": "",
        "description": description,
        "photos": [],
        "img_src": "",
        "lat": lat,
        "lon": lon,
        "total_area": total_area,
        "floor": floor,
        "build_year": build_year,
        "avito_id": item_id,
    }
