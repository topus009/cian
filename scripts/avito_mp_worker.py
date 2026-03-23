# -*- coding: utf-8 -*-
"""
Воркер для multiprocessing (spawn на Windows): импортируется как модуль, не как __main__.
"""
from __future__ import annotations

import sys
import time
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)


def worker_entry(payload: tuple) -> list[dict]:
    from selenium.common.exceptions import InvalidSessionIdException, WebDriverException

    from fetch_avito_offers_selenium import create_driver, process_one, avito_item_id

    (
        worker_index,
        chunk,
        no_images,
        save_html,
        delay,
        interactive,
        headless,
    ) = payload
    records: list[dict] = []
    driver = None
    try:
        driver = create_driver(headless=headless)
    except RuntimeError as e:
        print(f"[воркер {worker_index}] {e}", flush=True)
        return records
    try:
        for i, url in enumerate(chunk):
            aid = avito_item_id(url)
            if not aid:
                continue
            print(
                f"[воркер {worker_index}] [{i+1}/{len(chunk)}] {aid} …",
                flush=True,
            )
            rec = None
            try:
                rec = process_one(
                    driver,
                    url,
                    aid,
                    no_images,
                    save_html,
                    interactive=interactive,
                    headless=headless,
                )
            except (InvalidSessionIdException, WebDriverException):
                print(
                    f"[воркер {worker_index}] сессия Chrome — перезапуск…",
                    flush=True,
                )
                try:
                    driver.quit()
                except Exception:
                    pass
                driver = None
                try:
                    driver = create_driver(headless=headless)
                except RuntimeError as e2:
                    print(f"[воркер {worker_index}] {e2}", flush=True)
                    break
                rec = process_one(
                    driver,
                    url,
                    aid,
                    no_images,
                    save_html,
                    interactive=interactive,
                    headless=headless,
                )
            except Exception as ex:
                print(f"[воркер {worker_index}] ошибка {aid}: {ex}", flush=True)

            if rec:
                records.append(rec)
                print(f"[воркер {worker_index}] OK {aid}", flush=True)
            else:
                print(f"[воркер {worker_index}] пропуск {aid}", flush=True)
            time.sleep(delay)
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass
    return records
