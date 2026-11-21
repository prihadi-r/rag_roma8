#!/usr/bin/env python3
"""Ubah Strong's Greek dictionary (Open Scriptures .dat) menjadi JSON ringkas.

Sumber: https://github.com/openscriptures/strongs — Public Domain.
Keluaran dipakai modul Odoo untuk menyusun `embed_text` (gloss tiap kata),
sehingga pertanyaan berbahasa Indonesia bisa bertemu kata Yunani.

    python3 scripts/build_strongs_gloss.py
    → module/rag_teologi/data/strongs_greek.json
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUMBER = ROOT / "data" / "lexicon" / "strongsgreek.dat"
KELUARAN = ROOT / "module" / "rag_teologi" / "data" / "strongs_greek.json"

# "$$T0002631" memulai satu entri
_PENANDA = re.compile(r"^\$\$T(\d+)$")
# " 2631  katakrima  kat-ak'-ree-mah"
_KEPALA = re.compile(r"^\s*(\d+)\s+(\S+)\s+(\S.*)$")


_KURUNG = re.compile(r"\([^)]*\)")


def _rapikan(teks: str) -> str:
    """Bersihkan gloss gaya KJV agar layak masuk teks embedding."""
    teks = re.sub(r"\bCompare \d+.*$", "", teks, flags=re.I)
    teks = _KURUNG.sub("", teks)
    teks = teks.replace("+ ", "").replace(" -", "-")
    bagian = [b.strip(" .;-+") for b in teks.split(",")]
    bagian = [b for b in bagian if b and len(b) > 1]
    return ", ".join(bagian[:4])[:80]


def parse(teks: str) -> dict[str, dict]:
    entri: dict[str, dict] = {}
    nomor = None
    for baris in teks.splitlines():
        cocok = _PENANDA.match(baris)
        if cocok:
            nomor = str(int(cocok.group(1)))
            entri[nomor] = {"lemma": "", "ucap": "", "gloss": "", "def": ""}
            continue
        if nomor is None:
            continue
        if baris.startswith("\\0"):
            continue
        if not entri[nomor]["lemma"]:
            kepala = _KEPALA.match(baris)
            if kepala:
                entri[nomor]["lemma"] = kepala.group(2)
                entri[nomor]["ucap"] = kepala.group(3).strip()
                continue
        if baris.startswith(" ") or baris.startswith("\t"):
            isi = baris.strip()
            if not isi or isi.startswith("see "):
                continue
            entri[nomor]["def"] = (entri[nomor]["def"] + " " + isi).strip()
    # gloss = bagian setelah ":--" (gaya KJV), kalau tidak ada pakai definisi
    for data in entri.values():
        definisi = data["def"]
        if ":--" in definisi:
            mentah = definisi.split(":--", 1)[1]
        else:
            mentah = definisi.split(";", 1)[0]
        data["gloss"] = _rapikan(mentah)
        data["def"] = definisi.split(";", 1)[-1].strip()[:200]
    return {k: v for k, v in entri.items() if v["lemma"]}


def main() -> int:
    if not SUMBER.exists():
        raise SystemExit(
            f"sumber tidak ada: {SUMBER}\n"
            "unduh dulu:\n"
            "  curl -sL -o data/lexicon/strongsgreek.dat "
            "https://raw.githubusercontent.com/openscriptures/strongs/master/greek/strongsgreek.dat"
        )
    entri = parse(SUMBER.read_text(encoding="utf-8", errors="replace"))
    KELUARAN.parent.mkdir(parents=True, exist_ok=True)
    KELUARAN.write_text(
        json.dumps(
            {
                "sumber": "Strong's Greek Dictionary, Public Domain (Open Scriptures)",
                "jumlah": len(entri),
                "entri": entri,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    ukuran = KELUARAN.stat().st_size
    print(f"entri  : {len(entri)}")
    print(f"berkas : {KELUARAN} ({ukuran:,} bytes)")
    for n in ("2631", "4151", "4561", "26", "3551"):
        if n in entri:
            print(f"  G{n}: {entri[n]['lemma']} → {entri[n]['gloss']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
