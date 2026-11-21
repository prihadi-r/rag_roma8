#!/usr/bin/env python3
"""Tangkap layar UI RAG Teologi untuk USER_GUIDE.

Dijalankan di server (Chrome + playwright), bukan di laptop:

    /home/nms/guidetools/bin/python scripts/capture_screenshots.py

Memerlukan pengguna uji (lihat docs/USER_GUIDE source) dan Odoo hidup di
http://127.0.0.1:8069 dengan database rag_roma8.
"""
from __future__ import annotations

import os
import sys

from playwright.sync_api import sync_playwright

BASE = os.environ.get("RAG_BASE", "http://127.0.0.1:8069")
DB = os.environ.get("RAG_DB", "rag_roma8")
LOGIN = os.environ.get("RAG_LOGIN", "panduan@local")
PASSWORD = os.environ.get("RAG_PASS", "Panduan2026!")
OUT = os.environ.get("RAG_SHOTS", "/home/nms/rag-guide-shots")

# id aksi dari ir_model_data
AKSI = {
    'ayat': 90,
    'varian': 92,
    'chunk': 91,
    'config': 93,
    'perikop': 89,
    'log': 96,
    'wizard': 101,
    'ekspansi': 102,
}

gagal = []


def catat(page, nama):
    path = os.path.join(OUT, nama)
    page.screenshot(path=path)
    print(f"  ✓ {nama} ({os.path.getsize(path) // 1024} KB)")


def coba(label, fn):
    try:
        fn()
    except Exception as exc:  # noqa: BLE001
        gagal.append(f"{label}: {type(exc).__name__}: {exc}")
        print(f"  ✗ {label}: {type(exc).__name__}: {str(exc)[:160]}")


def buka_aksi(page, kunci):
    page.goto(f"{BASE}/odoo/action-{AKSI[kunci]}")
    page.wait_for_timeout(3500)


def cari(page, teks):
    kotak = page.locator(".o_searchview_input").first
    kotak.click()
    kotak.fill(teks)
    page.keyboard.press("Enter")
    page.wait_for_timeout(2500)


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(viewport={"width": 1680, "height": 980}, locale="id-ID")
        page = ctx.new_page()
        page.set_default_timeout(20000)

        print("masuk Odoo…")
        page.goto(f"{BASE}/web/login?db={DB}")
        page.fill("#login", LOGIN)
        page.fill("#password", PASSWORD)
        page.click("button[type=submit]")
        page.wait_for_url("**/odoo**", timeout=60000)
        page.wait_for_timeout(4000)

        # 1 — menu utama
        def menu():
            page.get_by_text("RAG Teologi", exact=True).first.click()
            page.wait_for_timeout(1200)
            catat(page, "01-menu.png")
            page.keyboard.press("Escape")
            page.wait_for_timeout(500)
        coba("menu", menu)

        # 2 — daftar ayat
        def daftar_ayat():
            buka_aksi(page, 'ayat')
            catat(page, "02-daftar-ayat.png")
        coba("daftar ayat", daftar_ayat)

        # 3 — form ayat 8:29
        def form_ayat():
            buka_aksi(page, 'ayat')
            cari(page, "Roma 8:29")
            page.locator(".o_data_row").first.click()
            page.wait_for_timeout(3000)
            catat(page, "03-form-ayat.png")
        coba("form ayat", form_ayat)

        # 4 — daftar varian
        def daftar_varian():
            buka_aksi(page, 'varian')
            catat(page, "04-varian.png")
        coba("varian", daftar_varian)

        # 5 — pengaturan RAG
        def config():
            page.goto(f"{BASE}/odoo/action-{AKSI['config']}/1")
            page.wait_for_timeout(3500)
            catat(page, "05-pengaturan-rag.png")
        coba("pengaturan", config)

        # 6 — daftar chunk
        def chunk():
            buka_aksi(page, 'chunk')
            catat(page, "06-chunk.png")
        coba("chunk", chunk)

        # 7 — ekspansi kueri
        def ekspansi():
            buka_aksi(page, 'ekspansi')
            catat(page, "07-ekspansi.png")
        coba("ekspansi", ekspansi)

        # 8 — konsol tanya jawab (menjalankan kueri cepat)
        def konsol():
            page.goto(f"{BASE}/odoo/action-{AKSI['wizard']}")
            page.wait_for_timeout(3000)
            area = page.locator("textarea").first
            area.click()
            area.fill("Roma 8:15")
            page.get_by_role("button", name="Tanya").first.click()
            print("  … menunggu jawaban LLM (bisa 60 detik)")
            page.wait_for_selector("text=Pencarian Langsung", timeout=240000)
            page.wait_for_timeout(1500)
            catat(page, "08-konsol.png")
        coba("konsol", konsol)

        # 9 — riwayat kueri, tab teks asli
        def riwayat():
            page.goto(f"{BASE}/odoo/action-{AKSI['log']}/27")
            page.wait_for_timeout(3500)
            catat(page, "09-riwayat-jawaban.png")
            page.locator("a.nav-link", has_text="Teks Asli").first.click()
            page.wait_for_timeout(1200)
            catat(page, "10-riwayat-teks-asli.png")
        coba("riwayat", riwayat)

        browser.close()

    print()
    if gagal:
        print(f"{len(gagal)} langkah gagal:")
        for g in gagal:
            print("  -", g)
        return 1
    print("semua tangkapan layar berhasil")
    return 0


if __name__ == "__main__":
    sys.exit(main())
