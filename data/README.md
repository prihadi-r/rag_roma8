# Dataset Roma 8:1–39

Dihasilkan oleh [`scripts/fase1_build.py`](../scripts/fase1_build.py) dari berkas mentah di `raw/`.
Jangan menyunting berkas di sini secara manual — ubah skrip lalu jalankan ulang.

## Berkas

| Berkas | Isi |
|---|---|
| `roma8.json` | dataset lengkap: teks, kata per kata (Strong's + parsing), varian, perikop |
| `roma8.csv` | tabel datar untuk pemeriksaan cepat (tanpa morfologi) |
| `roma8_variants.csv` | 21 baris varian tekstual hasil urai apparatus RP |
| `istilah-kunci.csv` | 27 istilah teologis + ayat kemunculannya (berdasarkan Strong's) |
| `VERIFIKASI.md` | laporan kelengkapan yang dihasilkan otomatis |

## Struktur `roma8.json`

```jsonc
{
  "meta": { "sumber": { "yunani": {...}, "inggris": {...}, "indonesia": {...} } },
  "ayat": [
    {
      "ref": "Roma 8:1",
      "chapter": 8,
      "verse": 1,
      "pericope": { "range": "8:1-11", "title_id": "Hidup oleh Roh", "title_en": "Life in the Spirit" },
      "paragraph_start": false,        // ¶ pada edisi RP
      "greek_accented": "Οὐδὲν ἄρα νῦν κατάκριμα ...",
      "greek_stripped": "ουδεν αρα νυν κατακριμα ...",
      "transliteration": "ouden ara nyn katakrima ...",
      "words": [
        { "surface": "ουδεν", "strongs": "3762", "morph": "A-NSN-N", "alt": [] }
      ],
      "word_count": 15,
      "kjv": "There is therefore now no condemnation ...",   // kurung siku dibuka
      "kjv_raw": "[There is] therefore now ...",              // apa adanya
      "ind": "Karena itu, sekarang tidak ada lagi penghukuman ...",
      "variants": [
        { "verse": 1, "seq": 1, "witness": "NA", "type": "omission",
          "byz_text": "μὴ κατὰ σάρκα περιπατοῦσιν ἀλλὰ κατὰ πνεῦμα",
          "other_text": "-",
          "apparatus_note": "{NA μὴ κατὰ σάρκα περιπατοῦσιν ἀλλὰ κατὰ πνεῦμα > - }" }
      ],
      "content_hash": "2b0ec792..."
    }
  ]
}
```

## Sumber & lisensi

| Bahasa | Edisi | Lisensi | Atribusi wajib |
|---|---|---|---|
| Yunani | Robinson-Pierpont 2018 (Byzantine Textform) | **Public Domain** | — |
| Inggris | King James Version 1769 | **Public Domain** (di luar Inggris) | — |
| Indonesia | **AYT — Alkitab Yang Terbuka** | CC (YLSA-AYT) — **non-komersial** | `AYT © 2011–2024 YLSA-AYT` |

### ⚠️ Catatan tentang AYT

- AYT **bukan** TB/LAI. Teksnya berbeda, mis. 8:1: AYT *"Karena itu, sekarang tidak ada lagi penghukuman…"* vs TB *"Demikianlah sekarang tidak ada penghukuman…"*.
- AYT dipakai karena LAI belum memberi kunci API. Bila kunci diperoleh, kolom `ind` dapat diganti tanpa mengubah struktur dataset.
- Berkas `about` AYT menyebut turunan berlisensi **BY-NC-SA**, sementara halaman eBible menyebut **BY-ND 4.0**. Keduanya mengizinkan penggunaan non-komersial **dengan atribusi**; perbedaan ada pada izin membuat turunan. Simpan atribusi di UI.
- Nama "AYT" dan "Alkitab Yang Terbuka" adalah merek dagang YLSA.

## Aturan yang diterapkan

1. **`¶` dipisahkan**, tidak dibuang — menjadi `paragraph_start` (muncul di 8:12, 18, 26, 31).
2. **Kurung siku KJV dibuka**: `kjv` bersih, `kjv_raw` menyimpan aslinya. Kata sisipan penerjemah tidak boleh hilang tanpa jejak.
3. **Parsing alternatif dipertahankan**: 8:28 `παντα` punya dua parsing (`A-APN` dan `A-NPN`) — keduanya disimpan, yang kedua di `alt`.
4. **Apparatus diurai menjadi data**, bukan disisakan di teks: 21 varian (18 substitusi, 3 omit).
5. **`content_hash`** memungkinkan deteksi perubahan tanpa membandingkan seluruh teks.

## Reproduksi

```bash
python3 scripts/fase1_build.py     # menulis ulang data/ dan VERIFIKASI.md
```

Berkas mentah perlu ada di `data/raw/` (lihat [`docs/SUMBER-TEKS.md`](../docs/SUMBER-TEKS.md) untuk URL unduhan).
