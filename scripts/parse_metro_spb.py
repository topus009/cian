# -*- coding: utf-8 -*-
"""
Парсинг таблицы станций метро СПб (Википедия).
Читает HTML из файла или stdin, выводит JSON: [{ "name", "lat", "lon", "line_color" }].
Строки без координат пропускаются.
Использование:
  python parse_metro_spb.py [путь к .html]
  python parse_metro_spb.py --fetch   # загрузить страницу с Википедии
"""
import re
import json
import sys
from pathlib import Path

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Установите: pip install beautifulsoup4", file=sys.stderr)
    sys.exit(1)

try:
    import requests
except ImportError:
    requests = None

WIKI_URL = 'https://ru.wikipedia.org/wiki/Список_станций_Петербургского_метрополитена'
HEX_RE = re.compile(r'#([0-9a-fA-F]{6})\b')
# Координаты в URL markdown-версии: Map/14/LAT/LON/ru
MAP_URL_RE = re.compile(r'Map/14/(\d+\.?\d*)/(\d+\.?\d*)/')
# Первая ссылка в строке — название станции: [Название](url)
FIRST_LINK_RE = re.compile(r'\|\s*\[([^\]]+)\]\([^)]+\)')

# Цвета линий СПб метро по порядку станций в таблице (К-В, М-П, Н-В, Правобер., Ф-П)
LINE_COLORS = (
    ['#d6083b'] * 18 +   # Кировско-Выборгская
    ['#0078c9'] * 18 +   # Московско-Петроградская
    ['#009a49'] * 12 +   # Невско-Василеостровская
    ['#ea7125'] * 10 +   # Правобережная
    ['#702785'] * 20     # Фрунзенско-Приморская
)


def parse_metro_markdown(text: str):
    """Парсинг markdown-таблицы (например, сохранённая страница Вики)."""
    out = []
    for line in text.splitlines():
        m = MAP_URL_RE.search(line)
        if not m:
            continue
        try:
            lat = round(float(m.group(1)), 6)
            lon = round(float(m.group(2)), 6)
        except ValueError:
            continue
        name_match = FIRST_LINK_RE.search(line)
        name = (name_match.group(1).strip() if name_match else '').strip()
        if not name or len(name) > 80:
            continue
        idx = len(out)
        line_color = LINE_COLORS[idx] if idx < len(LINE_COLORS) else '#702785'
        out.append({'name': name, 'lat': lat, 'lon': lon, 'line_color': line_color})
    return out


def parse_metro_table(html: str):
    soup = BeautifulSoup(html, 'html.parser')
    tbody = soup.find('tbody')
    if not tbody:
        return []
    out = []
    for tr in tbody.find_all('tr'):
        tds = tr.find_all('td')
        if len(tds) < 2:
            continue
        # Цвет линии — первый td, style (первый hex)
        line_color = None
        first_td = tds[0]
        style = first_td.get('style') or ''
        m = HEX_RE.search(style)
        if m:
            line_color = '#' + m.group(1)
        if not line_color:
            line_color = '#888888'
        # Название — второй td, первый <a>
        name = None
        second_td = tds[1]
        a = second_td.find('a')
        if a:
            name = (a.get_text() or '').strip()
        if not name:
            continue
        # Координаты — любой <a> с data-lat и data-lon
        lat, lon = None, None
        for a in tr.find_all('a', attrs={'data-lat': True, 'data-lon': True}):
            try:
                lat = float(a['data-lat'])
                lon = float(a['data-lon'])
                break
            except (TypeError, ValueError):
                continue
        if lat is None or lon is None:
            continue
        out.append({
            'name': name,
            'lat': round(lat, 6),
            'lon': round(lon, 6),
            'line_color': line_color,
        })
    return out


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--fetch':
        if not requests:
            print("Для --fetch нужен requests: pip install requests", file=sys.stderr)
            sys.exit(1)
        r = requests.get(WIKI_URL, headers={'User-Agent': 'Mozilla/5.0'})
        r.raise_for_status()
        html = r.text
        data = parse_metro_table(html)
    elif len(sys.argv) > 1:
        path = Path(sys.argv[1])
        text = path.read_text(encoding='utf-8')
        # Если в файле есть HTML-таблица — парсим её, иначе markdown
        if '<tbody>' in text or 'data-lat=' in text:
            data = parse_metro_table(text)
        else:
            data = parse_metro_markdown(text)
    else:
        text = sys.stdin.read()
        if '<tbody>' in text or 'data-lat=' in text:
            data = parse_metro_table(text)
        else:
            data = parse_metro_markdown(text)
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
