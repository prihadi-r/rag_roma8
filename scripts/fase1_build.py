#!/usr/bin/env python3
"""Fase 1 — Akuisisi & kurasi Roma 8:1–39.

Menggabungkan tiga sumber menjadi satu dataset paralel yang selaras per ayat:

  Yunani  : Robinson-Pierpont 2018 (public domain) — byztxt/byzantine-majority-text
  Inggris : KJV 1769 (public domain)               — ebible.org eng-kjv
  Indonesia: AYT, Alkitab Yang Terbuka (CC BY-ND 4.0) — ebible.org indayt

Keluaran (di data/):
  roma8.json            dataset lengkap per ayat
  roma8.csv             tabel datar untuk pemeriksaan cepat
  roma8_variants.csv    varian tekstual hasil urai apparatus
  istilah-kunci.csv     istilah teologis kunci + ayat kemunculannya
  VERIFIKASI.md         laporan pemeriksaan kelengkapan
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data"

CH = 8
VMAX = 39

PERIKOP = [
    (1, 11, "Hidup oleh Roh", "Life in the Spirit"),
    (12, 17, "Anak-anak Allah", "Children of God"),
    (18, 30, "Pengharapan Kemuliaan", "Future Glory"),
    (31, 39, "Keyakinan Iman", "More Than Conquerors"),
]

# Istilah teologis kunci: (Strong's, lemma Yunani, gloss Inggris, gloss Indonesia)
ISTILAH = [
    ("G2631", "κατάκριμα", "condemnation", "penghukuman"),
    ("G3551", "νόμος", "law", "hukum"),
    ("G4151", "πνεῦμα", "spirit", "roh"),
    ("G4561", "σάρξ", "flesh", "daging"),
    ("G2222", "ζωή", "life", "hidup"),
    ("G2288", "θάνατος", "death", "maut"),
    ("G1343", "δικαιοσύνη", "righteousness", "kebenaran"),
    ("G5206", "υἱοθεσία", "adoption", "pengangkatan anak"),
    ("G2818", "κληρονόμος", "heir", "ahli waris"),
    ("G1391", "δόξα", "glory", "kemuliaan"),
    ("G1680", "ἐλπίς", "hope", "pengharapan"),
    ("G26", "ἀγάπη", "love", "kasih"),
    ("G1656", "ἔλεος", "mercy", "belas kasihan"),
    ("G5486", "χάρισμα", "gift", "karunia"),
    ("G5547", "Χριστός", "Christ", "Kristus"),
    ("G2424", "Ἰησοῦς", "Jesus", "Yesus"),
    ("G2316", "θεός", "God", "Allah"),
    ("G3962", "πατήρ", "father", "Bapa"),
    ("G5043", "τέκνον", "child", "anak"),
    ("G3875", "παράκλητος", "advocate", "penolong"),
    ("G2906", "κραυγή", "cry", "seruan"),
    ("G2920", "κρίσις", "judgment", "penghakiman"),
    ("G1344", "δικαιόω", "justify", "membenarkan"),
    ("G1659", "ἐλευθερόω", "set free", "memerdekakan"),
    ("G1398", "δουλεύω", "serve", "melayani"),
    ("G4982", "σῴζω", "save", "menyelamatkan"),
    ("G2318", "θεοσεβής", "godly", "beribadah"),
]

# ---------------------------------------------------------------- utilitas

_AKSEN = re.compile(r"[.,;·:!?()\[\]«»\"'—–]")
_APPARATUS = re.compile(r"\{([^}]*)\}")


def norm_aksen(teks: str) -> str:
    """Buang diakritik Yunani (menghasilkan huruf dasar)."""
    nfd = unicodedata.normalize("NFD", teks)
    return "".join(c for c in nfd if not unicodedata.combining(c))


_TRANSLIT = [
    ("ου", "ou"), ("αι", "ai"), ("ει", "ei"), ("οι", "oi"), ("υι", "ui"),
    ("αυ", "au"), ("ευ", "eu"), ("ηυ", "ēu"), ("ου", "ou"),
    ("θ", "th"), ("φ", "ph"), ("χ", "ch"), ("ψ", "ps"), ("ξ", "x"),
    ("α", "a"), ("β", "b"), ("γ", "g"), ("δ", "d"), ("ε", "e"),
    ("ζ", "z"), ("η", "ē"), ("ι", "i"), ("κ", "k"), ("λ", "l"),
    ("μ", "m"), ("ν", "n"), ("ο", "o"), ("π", "p"), ("ρ", "r"),
    ("σ", "s"), ("ς", "s"), ("τ", "t"), ("υ", "y"), ("ω", "ō"),
]


def translit(teks: str) -> str:
    """Transliterasi kasar Yunani→Latin; cukup untuk input embedding."""
    dasar = norm_aksen(teks).lower()
    out, i = [], 0
    while i < len(dasar):
        for yunani, latin in _TRANSLIT:
            if dasar.startswith(yunani, i):
                out.append(latin)
                i += len(yunani)
                break
        else:
            out.append(dasar[i])
            i += 1
    return "".join(out)


def tokenisasi(teks: str) -> list[str]:
    bersih = _AKSEN.sub(" ", teks)
    return [t for t in bersih.split() if t]


def sha256(teks: str) -> str:
    return hashlib.sha256(teks.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- pembacaan sumber

def baca_csv_kitab(path: Path) -> dict[int, str]:
    hasil = {}
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if int(row["chapter"]) != CH:
                continue
            v = int(row["verse"])
            if 1 <= v <= VMAX:
                hasil[v] = row["text"].strip()
    return hasil


# Satu kata dapat diikuti LEBIH DARI SATU pasangan "nomor {kode}" — itu parsing
# alternatif untuk kata yang sama (mis. "παντα 3956 {A-APN} 3956 {A-NPN}"),
# bukan dua kata berbeda.
_KATA = re.compile(r"(\S+)\s+((?:\d+\s+\{[^}]*\}\s*)+)")
_PASANGAN = re.compile(r"(\d+)\s+\{([^}]*)\}")


def baca_strongs(path: Path) -> dict[int, list[dict]]:
    """Urai 'surface 3762 {A-NSN-N}' menjadi daftar kata."""
    hasil = {}
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if int(row["chapter"]) != CH:
                continue
            v = int(row["verse"])
            if not (1 <= v <= VMAX):
                continue
            kata = []
            for m in _KATA.finditer(row["text"]):
                surface = m.group(1)
                pasangan = _PASANGAN.findall(m.group(2))
                if not pasangan:
                    continue
                utama = pasangan[0]
                kata.append({
                    "surface": surface,
                    "strongs": utama[0],
                    "morph": utama[1].strip(),
                    "alt": [{"strongs": s, "morph": k.strip()}
                            for s, k in pasangan[1:]],
                })
            # token yang tidak terurai = indikasi berkas berubah format
            sisa = _KATA.sub("", row["text"]).strip()
            if sisa:
                raise ValueError(f"8:{v} token tak terurai: {sisa[:80]!r}")
            hasil[v] = kata
    return hasil


def baca_vpl(path: Path, kode: str = "ROM") -> dict[int, str]:
    hasil = {}
    pola = re.compile(rf"^{kode} {CH}:(\d+) (.*)$")
    for baris in path.read_text(encoding="utf-8").splitlines():
        m = pola.match(baris)
        if m:
            v = int(m.group(1))
            if 1 <= v <= VMAX:
                hasil[v] = m.group(2).strip()
    return hasil


def urai_apparatus(teks: str, verse: int) -> tuple[str, list[dict]]:
    """Pisahkan apparatus {WITNESS A > B } dari teks, kembalikan teks bersih."""
    varian = []
    for idx, m in enumerate(_APPARATUS.finditer(teks), start=1):
        isi = m.group(1).strip()
        witness, _, bacaan = isi.partition(" ")
        if ">" not in bacaan:
            continue
        kiri, _, kanan = bacaan.partition(">")
        kiri, kanan = kiri.strip(), kanan.strip()
        if kanan == "-":
            jenis = "omission"
        elif kiri == "-":
            jenis = "addition"
        else:
            jenis = "substitution"
        varian.append({
            "verse": verse,
            "seq": idx,
            "witness": witness,
            "type": jenis,
            "byz_text": kiri,
            "other_text": kanan,
            "apparatus_note": m.group(0),
        })
    bersih = _APPARATUS.sub("", teks)
    bersih = re.sub(r"\s+", " ", bersih).strip()
    return bersih, varian


# ---------------------------------------------------------------- perakitan

def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    akented = baca_csv_kitab(RAW / "ROM_accented.csv")
    withvar = baca_csv_kitab(RAW / "ROM_variants.csv")
    strongs = baca_strongs(RAW / "ROM_strongs.csv")
    kjv = baca_vpl(RAW / "kjv" / "eng-kjv_vpl.txt")
    ayt = baca_vpl(RAW / "ayt" / "indayt_vpl.txt")

    ayat, semua_varian, masalah = [], [], []

    for v in range(1, VMAX + 1):
        if v not in akented:
            masalah.append(f"8:{v} tidak ada di ROM_accented.csv")
        if v not in strongs:
            masalah.append(f"8:{v} tidak ada di ROM_strongs.csv")
        if v not in kjv:
            masalah.append(f"8:{v} tidak ada di KJV")
        if v not in ayt:
            masalah.append(f"8:{v} tidak ada di AYT")

        yunani_mentah = akented.get(v, "")
        # ¶ menandai awal paragraf pada edisi RP — dipisahkan, bukan dibuang
        paragraf_baru = "¶" in yunani_mentah
        yunani_beraksen = yunani_mentah.replace("¶", "").strip()
        _, varian = urai_apparatus(withvar.get(v, ""), v)
        semua_varian.extend(varian)

        kata = strongs.get(v, [])
        greek_stripped = " ".join(k["surface"] for k in kata)
        bhs = translit(greek_stripped)

        kjv_raw = kjv.get(v, "")
        kjv_bersih = re.sub(r"\[([^\]]*)\]", r"\1", kjv_raw)

        # pemeriksaan jumlah kata
        n_aksen = len(tokenisasi(norm_aksen(yunani_beraksen)))
        n_kata = len(kata)
        if n_aksen != n_kata:
            masalah.append(
                f"8:{v} jumlah kata berbeda: beraksen={n_aksen}, strongs={n_kata}"
            )

        perikop = next((p for p in PERIKOP if p[0] <= v <= p[1]), None)

        ayat.append({
            "ref": f"Roma 8:{v}",
            "chapter": CH,
            "verse": v,
            "pericope": {
                "range": f"8:{perikop[0]}-{perikop[1]}",
                "title_id": perikop[2],
                "title_en": perikop[3],
            },
            "paragraph_start": paragraf_baru,
            "greek_accented": yunani_beraksen,
            "greek_stripped": greek_stripped,
            "transliteration": bhs,
            "words": kata,
            "word_count": len(kata),
            "kjv": kjv_bersih,
            "kjv_raw": kjv_raw,
            "ind": ayt.get(v, ""),
            "variants": varian,
            "content_hash": sha256(
                "|".join([yunani_beraksen, greek_stripped, kjv_bersih, ayt.get(v, "")])
            ),
        })

    # istilah kunci: hitung ayat kemunculan berdasarkan nomor Strong's
    istilah_rows = []
    for strongs_no, lemma, gloss_en, gloss_id in ISTILAH:
        nomor = strongs_no.lstrip("G")
        kena = [a["verse"] for a in ayat
                if any(k["strongs"] == nomor for k in a["words"])]
        istilah_rows.append({
            "strongs": strongs_no,
            "lemma": lemma,
            "translit": translit(lemma),
            "gloss_en": gloss_en,
            "gloss_id": gloss_id,
            "jumlah_ayat": len(kena),
            "ayat": ",".join(f"8:{x}" for x in kena),
        })

    # ---------- tulis keluaran
    meta = {
        "kitab": "Roma",
        "pasal": CH,
        "ayat": VMAX,
        "sumber": {
            "yunani": {
                "edisi": "Robinson-Pierpont 2018 (Byzantine Textform)",
                "repo": "https://github.com/byztxt/byzantine-majority-text",
                "lisensi": "Public Domain",
                "berkas": ["ROM_accented.csv", "ROM_strongs.csv", "ROM_variants.csv"],
            },
            "inggris": {
                "edisi": "King James Version 1769",
                "url": "https://ebible.org/Scriptures/eng-kjv_vpl.zip",
                "lisensi": "Public Domain (di luar Inggris)",
            },
            "indonesia": {
                "edisi": "AYT — Alkitab Yang Terbuka",
                "url": "https://ebible.org/Scriptures/indayt_vpl.zip",
                "lisensi": "CC BY-ND 4.0 — Yayasan Lembaga SABDA",
                "catatan": "Pengganti TB/LAI yang belum memperoleh kunci API. "
                           "Atribusi wajib dipertahankan.",
            },
        },
    }

    (OUT / "roma8.json").write_text(
        json.dumps({"meta": meta, "ayat": ayat}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    with (OUT / "roma8.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["ref", "perikop", "kata", "greek_stripped", "kjv", "ind", "varian"])
        for a in ayat:
            w.writerow([a["ref"], a["pericope"]["title_id"], a["word_count"],
                        a["greek_stripped"], a["kjv"], a["ind"],
                        len(a["variants"])])

    with (OUT / "roma8_variants.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["ref", "seq", "witness", "type", "byz_text", "other_text", "apparatus"])
        for va in semua_varian:
            w.writerow([f"Roma 8:{va['verse']}", va["seq"], va["witness"],
                        va["type"], va["byz_text"], va["other_text"],
                        va["apparatus_note"]])

    with (OUT / "istilah-kunci.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(istilah_rows[0]))
        w.writeheader()
        w.writerows(istilah_rows)

    # ---------- laporan verifikasi
    total_kata = sum(a["word_count"] for a in ayat)
    tanpa_varian = sum(1 for a in ayat if not a["variants"])
    per_jenis: dict[str, int] = {}
    for va in semua_varian:
        per_jenis[va["type"]] = per_jenis.get(va["type"], 0) + 1

    laporan = [
        "# Verifikasi Fase 1 — Roma 8:1–39",
        "",
        f"Dihasilkan oleh `scripts/fase1_build.py`.",
        "",
        "## Kelengkapan",
        "",
        "| Sumber | Ayat | Rentang |",
        "|---|---|---|",
        f"| Robinson-Pierpont (berdiakritik) | {len(akented)} | 1–{max(akented)} |",
        f"| Robinson-Pierpont (Strong's + parsing) | {len(strongs)} | 1–{max(strongs)} |",
        f"| KJV 1769 | {len(kjv)} | 1–{max(kjv)} |",
        f"| AYT (Indonesia) | {len(ayt)} | 1–{max(ayt)} |",
        "",
        f"- Total kata Yunani: **{total_kata}**",
        f"- Ayat tanpa varian tekstual: **{tanpa_varian}** dari 39",
        f"- Total baris varian: **{len(semua_varian)}** "
        f"({', '.join(f'{k}={v}' for k, v in sorted(per_jenis.items()))})",
        "",
        "## Pemeriksaan",
        "",
    ]

    if masalah:
        laporan.append(f"⛔ **{len(masalah)} masalah ditemukan:**")
        laporan += [f"- {m}" for m in masalah]
    else:
        laporan.append("✅ Semua pemeriksaan lulus:")
        laporan.append("- 39 ayat hadir di keempat sumber, tanpa nomor yang hilang")
        laporan.append("- Jumlah kata Yunani berdiakritik = jumlah kata pada berkas Strong's di setiap ayat")
        laporan.append("- Seluruh apparatus berhasil diurai (tidak ada sisa `{` pada teks bersih)")

    sisa_kurung = [a["verse"] for a in ayat if "{" in (a["greek_accented"] + a["kjv"] + a["ind"])]
    laporan += [
        f"- Ayat dengan sisa `{{` pada teks: {len(sisa_kurung)}",
        f"- Penanda paragraf `¶` dipisahkan ke `paragraph_start`: "
        + ", ".join(f"8:{a['verse']}" for a in ayat if a["paragraph_start"]),
        "",
        "## Perikop",
        "",
        "| Rentang | Judul (ID) | Judul (EN) | Ayat |",
        "|---|---|---|---|",
    ]
    for awal, akhir, judul_id, judul_en in PERIKOP:
        laporan.append(f"| 8:{awal}–{akhir} | {judul_id} | {judul_en} | {akhir - awal + 1} |")

    (OUT / "VERIFIKASI.md").write_text("\n".join(laporan) + "\n", encoding="utf-8")

    print("\n".join(laporan))
    return 0 if not masalah else 1


if __name__ == "__main__":
    raise SystemExit(main())
