# Sumber Teks Roma 8:1–39 — Hasil Penelusuran & Verifikasi

Tanggal: 2026-11-21 · Status: **sumber ditemukan dan diuji unduh** untuk 2 dari 3 sumber; LAI butuh kunci API atau keputusan lisensi.

---

## 1. Ringkasan

| Sumber | Status | Lisensi | Format | Catatan |
|---|---|---|---|---|
| **Robinson-Pierpont** | ✅ siap, sudah diunduh | **Public Domain** | CSV Unicode | Tersedia berdiakritik, tanpa aksen, morfologi, Strong's, **dan apparatus varian** |
| **KJV** | ✅ siap, sudah diunduh | **Public Domain** (di luar Inggris) | VPL, USFM, USFX, Sword | Teks 1769; kata sisipan ditandai `[...]` |
| **LAI / TB** | ⚠️ butuh akses | **Berhak cipta LAI** | API resmi (butuh token) | 39 ayat = di bawah ambang izin; wajib atribusi |

Semua uji unduh dilakukan di server target, hasilnya tersimpan di `/home/nms/rag-roma8/src/`.

---

## 2. Robinson-Pierpont (Yunani Koine, Byzantine Textform)

**Repositori resmi:** [byztxt/byzantine-majority-text](https://github.com/byztxt/byzantine-majority-text)

Ini rumah resmi teks Dr. Maurice A. Robinson, berisi **edisi RP2018** (teks dimutakhirkan Juli 2023), lengkap dengan varian, parsing morfologi, dan nomor Strong's. Lisensi: *"All the code and text contained in this folder is in the Public Domain."*

### Empat varian berkas (semua tersedia per kitab, `ROM.csv` untuk Roma)

| Folder | Isi | Ukuran `ROM.csv` | Kegunaan untuk proyek |
|---|---|---|---|
| `csv-unicode/ccat/no-variants/` | **Berdiakritik**, teks bersih | 88.436 B | **teks Yunani utama** (yang dibaca manusia) |
| `csv-unicode/ccat/with-variants/` | **Berdiakritik + apparatus** | 99.063 B | **sumber varian tekstual** — kunci perbaikan §7 PLAN |
| `csv-unicode/strongs/with-parsing/` | **Tanpa aksen** + parsing + Strong's | 173.697 B | **stripped Greek** + morfologi/Strong's |
| `tei-xml-unicode/` | TEI-XML | — | hanya jika perlu kolasi CollateX |

### Contoh keluaran terverifikasi

`no-variants` (berdiakritik):
```csv
chapter,verse,text
8,1,"Οὐδὲν ἄρα νῦν κατάκριμα τοῖς ἐν χριστῷ Ἰησοῦ, μὴ κατὰ σάρκα περιπατοῦσιν, ἀλλὰ κατὰ πνεῦμα."
```

`strongs/with-parsing` (tanpa aksen, per kata):
```csv
8,1,ουδεν 3762 {A-NSN-N} αρα 686 {PRT} νυν 3568 {ADV} κατακριμα 2631 {N-NSN} τοις 3588 {T-DPM} ...
```

`with-variants` (**apparatus inline**):
```csv
8,1,"Οὐδὲν ἄρα νῦν κατάκριμα τοῖς ἐν χριστῷ Ἰησοῦ, μὴ {NA μὴ κατὰ σάρκα περιπατοῦσιν ἀλλὰ κατὰ πνεῦμα > - } κατὰ σάρκα περιπατοῦσιν, ἀλλὰ κατὰ πνεῦμα."
```

> **Temuan penting.** Notasi `{NA ... > - }` menandakan bahwa Nestle-Aland (teks eklektik yang mendasari TB/LAI) **menghilangkan** klausa tersebut. Artinya varian Roma 8:1 **sudah berupa data terstruktur**, tidak perlu disimpulkan LLM. Ini langsung menyelesaikan kegagalan yang tercatat di [BENCHMARK-LLAMA.md §7](BENCHMARK-LLAMA.md).

### Perintah unduh

```bash
BASE=https://raw.githubusercontent.com/byztxt/byzantine-majority-text/master/csv-unicode
curl -sLO $BASE/ccat/no-variants/ROM.csv
curl -sLO $BASE/ccat/with-variants/ROM.csv
curl -sLO $BASE/strongs/with-parsing/ROM.csv
```

Catatan: repositori memperingatkan agar **tidak memakai rilis Unicode sebelum 2.0.3** (ada galat konversi aksen). Pakai `master` atau rilis 3.x.

Alternatif: PDF resmi di [byzantinetext.com](https://www.byzantinetext.com) dan Internet Archive, tetapi PDF tidak cocok untuk ingestion.

---

## 3. KJV (King James Version)

**Sumber:** [eBible.org — eng-kjv](https://ebible.org/Scriptures/details.php?id=eng-kjv) · **Public Domain** (di luar Inggris; di Inggris hak cetak dipegang Cambridge/Oxford/Collins — tidak relevan untuk penggunaan digital di Indonesia)

Berkas yang dipakai: [`eng-kjv_vpl.zip`](https://ebible.org/Scriptures/eng-kjv_vpl.zip) (5,2 MB) — *verse-per-line*, paling mudah diparsing.

### Contoh keluaran terverifikasi

```
ROM 8:1 [There is] therefore now no condemnation to them which are in Christ Jesus, who walk not after the flesh, but after the Spirit.
ROM 8:2 For the law of the Spirit of life in Christ Jesus hath made me free from the law of sin and death.
```

Kurung siku `[...]` menandai kata yang **tidak ada dalam naskah Yunani** tetapi ditambahkan penerjemah — berguna untuk analisis, dan harus **dibuang** saat normalisasi teks.

### Format alternatif di halaman yang sama

| Format | Berkas | Kapan dipakai |
|---|---|---|
| VPL (verse-per-line) | `eng-kjv_vpl.zip` | ✅ **pilihan utama** — parsing termudah |
| USFM | `eng-kjv_usfm.zip` | bila butuh struktur kitab/pasal penuh |
| USFX | `eng-kjv_usfx.zip` | bila butuh XML |
| Sword module | `engKJV1769eb.zip` | bila memakai pustaka libsword |
| PDF / ePub | — | tidak untuk ingestion |

**KJV + Strong's** (opsional, untuk keselarasan leksikal): [CrossWire KJV](https://crosswire.org/sword/modules/ModInfo.jsp?modName=KJV) — "King James Version (1769) with Strongs Numbers and Morphology". Tidak wajib, karena Strong's sudah tersedia di sisi Yunani (RP).

---

## 4. LAI / Terjemahan Baru — **berhak cipta**

### 4.1 Kebijakan resmi ([alkitab.or.id/tentang-kami/penggunaan-teks](https://alkitab.or.id/tentang-kami/penggunaan-teks))

> Pengutipan/penggandaan untuk tujuan **non-komersial** … tidak memerlukan izin tertulis dari LAI, **asalkan tidak melebihi 1.000 ayat dan/atau tidak terdiri atas satu kitab** dalam Alkitab. Namun pada akhir kutipan harus dicantumkan pengakuan Hak Moral: **"Dikutip dari ALKITAB (TB) © LAI 1974"**
>
> Untuk tujuan **komersial**: batasnya 500 ayat, dengan atribusi yang sama.

**Penilaian untuk proyek ini:** Roma 8:1–39 = **39 ayat**, bukan satu kitab utuh, dan proyek ini untuk studi pribadi/skolaristik non-komersial. Secara kebijakan LAI, penggunaan ini **tidak memerlukan izin tertulis**, dengan syarat atribusi.

> ⚠️ Namun jika nanti modul Odoo ini **dibagikan** (repo publik, dijual, dipakai gereja lain), status "non-komersial" berubah dan penilaian hukumnya harus ditinjau ulang. Simpan atribusi di tabel database dan tampilkan di UI.

### 4.2 API resmi LAI (jalur paling tepat)

**Dokumentasi:** [bible-api.alkitab.or.id](https://bible-api.alkitab.or.id/) · Postman: [Bible API](https://documenter.getpostman.com/view/15253393/2sB3WwpwwD) · [Users & Auth](https://documenter.getpostman.com/view/15253393/2sB3Wwpx1W)

Terverifikasi diuji: tanpa token → **HTTP 400**. Wajib mendaftar dan memperoleh API key.

Bentuk endpoint (dari dokumentasi resmi):

```
GET https://bible-api.alkitab.or.id/bible-api/api/v1/bible/tb/roma/8
Authorization: Bearer <API_KEY>
Accept: application/json
```

Cara memperoleh kunci: ikuti dokumentasi Users/Auth, atau ajukan permohonan ke **info@alkitab.or.id** dengan menjelaskan konteks (riset/studi pribadi non-komersial). Halaman resmi menyebut API ini cocok untuk "chatbot dan sistem tanya jawab Alkitab" — persis kategori proyek ini.

### 4.3 Alternatif bila akses API lambat

| Sumber | Lisensi | Catatan |
|---|---|---|
| [SABDA](https://sabdaweb.sabda.org/copy/) | Non-komersial, milik YLSA | Uji langsung: `alkitab.sabda.org/api/passage` mengembalikan **HTML**, bukan JSON — perlu scraping, rapuh |
| [AYT — Alkitab Yang Terbuka](https://ebible.org/indayt/) | **CC BY-ND 4.0** | Bebas dipakai dengan atribusi; **tanpa turunan** (embedding = turunan?) dan terjemahan berbeda dari TB |
| Situs alkitab.or.id | Berhak cipta LAI | Halaman `cari-alkitab/tb/roma/8` merender teks via JavaScript — tidak bisa di-`curl` langsung |
| Aplikasi Bible.com / MEMRA | Berhak cipta LAI | Tidak ada akses massal legal |

**Rekomendasi:** ajukan permohonan API ke LAI. Bila ditolak atau lambat, opsi paling aman secara hukum adalah **memakai AYT** (CC BY-ND) sebagai teks Indonesia, atau memasukkan 39 ayat TB secara manual sebagai data riset pribadi dengan atribusi penuh.

### ✅ Keputusan (2026-11-21)

**AYT dipakai** sebagai teks Indonesia karena dapat diunduh langsung tanpa API. Sudah diimpor ke Odoo dan menjadi kolom `ind` pada 39 ayat. Atribusi `AYT © 2011–2024 YLSA-AYT` disimpan di dataset.

Bila kunci API LAI kelak diperoleh, cukup ganti kolom `ind` — struktur dataset dan modul tidak berubah. Perbedaan yang perlu diingat: AYT **bukan** TB, mis. 8:1 AYT *"Karena itu, sekarang tidak ada lagi penghukuman…"* vs TB *"Demikianlah sekarang tidak ada penghukuman…"*.

---

## 5. Rencana akuisisi Roma 8:1–39

| Langkah | Sumber | Tindakan |
|---|---|---|
| 1 | RP `no-variants/ROM.csv` | filter `chapter==8 && verse<=39` → teks berdiakritik |
| 2 | RP `strongs/with-parsing/ROM.csv` | filter sama → *stripped Greek* + Strong's + parsing |
| 3 | RP `with-variants/ROM.csv` | filter sama → **tabel varian** (klausa + arah NA/ECM) |
| 4 | KJV `eng-kjv_vpl.txt` | filter `ROM 8:` baris 1–39 → buang `[...]` |
| 5 | AYT `indayt_vpl.zip` ✅ (LAI API belum) | ambil ayat 1–39 + simpan atribusi |

Verifikasi wajib: 39 ayat di keempat kolom, jumlah kata Yunani cocok antara `no-variants` dan `strongs/with-parsing`, dan tidak ada nomor ayat yang hilang.

---

## 6. Catatan implementasi yang muncul dari sumber ini

1. **Dua bentuk teks Yunani dipakai bersamaan**, bukan satu: berdiakritik untuk tampilan/ sitasi, tanpa aksen untuk indeks `tsvector` dan pencarian. Kolom `stripped_greek` di modul bisa diisi langsung dari `strongs/with-parsing`, bukan hasil normalisasi runtime — lebih cepat dan konsisten.
2. **Strong's & parsing gratis dan lengkap** dari RP, sehingga tabel leksikon tidak perlu dibeli.
3. **Apparatus `with-variants` harus diurai** menjadi tabel tersendiri (`ref_chunk`, `variant_type`, `witness`), agar Query Router bisa menjawab pertanyaan varian tanpa LLM.
4. **Atribusi LAI wajib disimpan sebagai field**, bukan sekadar komentar kode, karena harus tampil di UI.

---

## 7. Berkas uji yang sudah ada di server

```
/home/nms/rag-roma8/src/
├── ROM.csv              (strongs/with-parsing, 173.697 B)
├── ROM_no-variants.csv  (berdiakritik, 88.436 B)
├── ROM_with-variants.csv(berdiakritik + apparatus, 99.063 B)
├── kjv.zip              (eng-kjv_vpl.zip, 5.227.895 B)
└── kjv/                 (hasil ekstrak: eng-kjv_vpl.txt, .xml, .sql)
```
