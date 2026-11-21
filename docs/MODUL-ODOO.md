# Modul Odoo `rag_teologi` — Fase 4

Status: **terpasang dan teruji** di `192.168.18.222` · Database `rag_roma8` · Odoo **18.2alpha1** (series 18.2)

---

## 1. Ringkasan

Modul `rag_teologi` adalah *self-contained RAG engine* di dalam Odoo: **17 tabel inti** (+3 tabel wizard sementara), 1 collection pencarian (`rag_chunk`), kolom `vector`/`tsvector` di luar ORM, dan pemisahan peran RAG User / RAG Manager.

Lokasi di server: `/opt/odoo18/addons/rag_teologi` (owner `odoo18:odoo18`).
Sumber di repo: [`module/rag_teologi/`](../module/rag_teologi).

---

## 2. ⚠️ Temuan penting: Odoo-nya bukan 18.0

`odoo --version` di laptop melaporkan 18.0, tetapi server menjalankan **18.2alpha1** (`odoo.release.version`). Ini bukan perbedaan kosmetik — dua API berubah dan sempat membuat instalasi gagal:

| Hal | 18.0 | 18.2 (server) | Akibat bila salah |
|---|---|---|---|
| Versi manifest | `18.0.x.y.z` | **`18.2.x.y.z`** | modul ditolak: *"incompatible version, setting installable=False"* |
| SQL constraint | `_sql_constraints = [...]` | **`nama = models.Constraint(sql, pesan)`** | atribut diabaikan, constraint tidak pernah dibuat |
| Log | — | `--without-demo` kini boolean | `--without-demo=all` memicu *invalid boolean value* |

---

## 3. Struktur berkas

```
rag_teologi/
├── __manifest__.py          depends: ['base'], data 7 berkas, post_init_hook
├── __init__.py
├── hooks.py                 DDL vector/tsvector + indeks (idempoten)
├── models/
│   ├── master.py            rag.chunk.kind, rag.witness, rag.variant.type, rag.query.route
│   ├── rag_book.py          rag.book
│   ├── rag_pericope.py      rag.pericope            (parent konteks)
│   ├── rag_verse.py         rag.verse               (child, sumber kebenaran)
│   ├── rag_chunk.py         rag.chunk               (collection: vektor + FTS)
│   ├── rag_variant.py       rag.variant             (varian tekstual)
│   ├── rag_config.py        rag.embedding.model, rag.prompt.template, rag.config
│   ├── rag_query.py         rag.query.log, rag.query.hit
│   └── rag_import.py        rag.import.batch
├── security/
│   ├── rag_security.xml     2 grup + 4 record rule
│   └── ir.model.access.csv  36 baris ACL
├── data/rag_master_data.xml data awal (noupdate)
└── views/                   25 view, 14 aksi, 8 berkas
```

---

## 4. Model dan tabel

| Model | Tabel | Peran |
|---|---|---|
| `rag.book` | `rag_book` | kitab |
| `rag.pericope` | `rag_pericope` | **parent** — unit konteks perikop |
| `rag.verse` | `rag_verse` | **child** — kebenaran kanonik teks |
| `rag.chunk` | `rag_chunk` | **collection** — vektor + 3 FTS |
| `rag.variant` | `rag_variant` | varian tekstual (bukan inferensi LLM) |
| `rag.config` | `rag_config` | parameter retrieval & LLM (singleton aktif) |
| `rag.embedding.model` | `rag_embedding_model` | dimensi & endpoint model |
| `rag.prompt.template` | `rag_prompt_template` | templat ber-versi |
| `rag.query.log` / `rag.query.hit` | `rag_query_log` / `rag_query_hit` | audit & dasar evaluasi |
| `rag.import.batch` | `rag_import_batch` | jejak impor |
| 4 master enumerasi | `rag_chunk_kind`, `rag_witness`, `rag_variant_type`, `rag_query_route` | referensi (bukan `Selection`) |

---

## 5. Kolom di luar ORM

Dibuat oleh [`hooks.py`](../module/rag_teologi/hooks.py), idempoten (`IF NOT EXISTS`), sehingga aman pada install maupun upgrade.

| Kolom | Tipe | Catatan |
|---|---|---|
| `rag_chunk.embedding` | `vector(1024)` | dimensi dikunci bge-m3 |
| `rag_chunk.fts_id` | `tsvector` generated | dari `lai_text` |
| `rag_chunk.fts_en` | `tsvector` generated | dari `kjv_text` |
| `rag_chunk.fts_gr` | `tsvector` generated | dari `greek_stripped` + `lexeme_text` |

Indeks: HNSW (`m=16, ef_construction=64`, `vector_cosine_ops`), 3× GIN `tsvector`, GIN trigram pada `greek_stripped`, indeks parsial `WHERE dirty` pada `rag_verse`/`rag_chunk`, dan indeks unik parsial `rag_config(active) WHERE active`.

### Hook tahan urutan

`_auto_init()` milik `rag.chunk` berjalan **sebelum** tabel `rag_config` ada, sehingga pembuatan indeks lintas-tabel akan gagal (`relation "rag_config" does not exist` — ini benar-benar terjadi saat pengembangan). Perbaikannya: fungsi memeriksa keberadaan tabel lebih dulu, lalu `post_init_hook(env)` memanggilnya sekali lagi setelah seluruh tabel selesai.

---

## 6. Keamanan

| Grup | Hak |
|---|---|
| **RAG User** | baca seluruh data referensi & ayat; buat/baca/ubah riwayat kueri **miliknya sendiri** |
| **RAG Manager** | semua di atas + CRUD master data, konfigurasi, impor, re-embed |

Record rule: `rag.query.log` dan `rag.query.hit` dibatasi `user_id = user.id` untuk RAG User; RAG Manager memakai domain `[(1,'=',1)]`. Karena aturan grup di-OR, manager otomatis melihat semua.

---

## 7. Perbedaan dari dokumen desain

| Desain | Implementasi | Alasan |
|---|---|---|
| field `display_name` pada chunk | **`label`** | `display_name` adalah field khusus Odoo; menimpanya menghasilkan `False` |
| `_sql_constraints` | `models.Constraint` | dihapus di 18.2 |
| versi `18.0.1.0.0` | `18.2.1.0.0` | server menjalankan 18.2 |
| `index=True` pada `dirty` | dihapus | indeks parsial `WHERE dirty` sudah ada; btree ganda tidak perlu |

---

## 8. Cara deploy

```bash
./scripts/deploy_module.sh              # unggah + upgrade + restart layanan
./scripts/deploy_module.sh --install    # install pertama kali
./scripts/deploy_module.sh --no-reload  # tanpa restart
```

Skrip memeriksa sintaks Python & XML, mengemas, mengunggah lewat SFTP, memasang ke addons, menjalankan `-i`/`-u` dengan `--stop-after-init --no-http`, lalu me-restart `odoo18.service`.

---

## 9. Hasil uji fungsional

Dijalankan via `odoo-bin shell` ([`module/tests/test_rag_module.py`](../module/tests/test_rag_module.py)), seluruh data uji di-*rollback*:

| # | Uji | Hasil |
|---|---|---|
| 1 | Buat perikop, label otomatis | `Roma 8:1–11 — Hidup oleh Roh` |
| 2 | Buat ayat, `word_count` dari JSON morfologi | 1 kata (uji), state `draft` |
| 3 | Label chunk | `Roma 8:1 [verse]` |
| 4 | Tulis vektor via SQL, set `embedded` | vektor + 4 kolom non-ORM terisi |
| 5 | Ubah teks ayat setelah embed | ayat → `chunked`, `dirty=True`, **chunk ikut kotor** |
| 6 | FTS Yunani `κατακριμα` | ditemukan |
| 7 | FTS Indonesia `penghukuman` | ditemukan |
| 8 | Cosine ke vektor sendiri | `1.0` |
| 9 | Varian NA/omission | tersimpan, `variant_count` terupdate |
| 10 | Query log + hit | `hit_count` benar, user tercatat |
| 11 | Konfigurasi aktif | `Roma 8 — lokal`, model `bge-m3-Q8_0` |
| 12 | Duplikat ayat & dua config aktif | **ditolak** database (`UniqueViolation`) |
| 13 | `-u rag_teologi` (upgrade) | 0 galat, state tetap `installed` |

---

## 10. Wizard impor (`rag.import.wizard`)

Ditambahkan pada Fase 5. Menerima berkas JSON (unggah) **atau** path di server, lalu mengisi `rag.book`, `rag.pericope`, `rag.verse`, dan `rag.variant`.

- **Idempoten** — data dicocokkan berdasarkan (kitab, pasal, ayat) dan (kitab, pasal, rentang); impor ulang memperbarui, bukan menggandakan.
- **Atomik per baris** — tiap ayat dibungkus savepoint; satu baris gagal tidak menggugurkan yang lain, dan galatnya dicatat di `rag.import.batch.log`.
- **Tidak melakukan chunking/embedding** — ayat sengaja tetap `state='draft'` dan `dirty=true`.
- Menu: *RAG Teologi → Konfigurasi → Impor Dataset…*

Hasil impor dataset Roma 8:

| Item | Jumlah |
|---|---|
| Kitab | 1 |
| Perikop | 4 (8:1–11, 12–17, 18–30, 31–39) |
| Ayat | 39 |
| Varian | 21 (18 substitusi, 3 omit) |
| Chunk | **0** (sengaja) |

---

## 11. Chunking engine & decoder morfologi (Fase 5)

### `models/morph.py` — decoder kode Robinson

Menerjemahkan kode seperti `V-PAP-DPM` menjadi *"verba, present, aktif, partisip, datif, plural, maskulin"*. Spesifikasi mengikuti `source/README.md` repositori byztxt. **146/146 kode** yang muncul di Roma 8 terurai.

Modul ini sengaja **tidak mengimpor Odoo**, sehingga bisa diuji dengan `python3 models/morph.py` tanpa database.

### `models/chunker.py` — komposisi `embed_text`

```
ID: Karena itu, sekarang tidak ada lagi penghukuman bagi orang …
EN: There is therefore now no condemnation …
YUNANI: ουδεν αρα νυν κατακριμα …
TRANS: ouden ara nyn katakrima …
LEMA: oudeis ara nun katakrima ho en Christos Iesous …
GLOSS: any, haught, condemnation, the, Christ, Jesus, carnal, flesh …
```

- Yunani **berdiakritik tidak** di-embed — dipakai bentuk tanpa aksen + transliterasi + lema + glos.
- Glos berasal dari **Strong's Greek Dictionary** (public domain, 5.624 entri) yang diolah `scripts/build_strongs_gloss.py`.
- `embed_hash` = sha256 dari `embed_text`, sehingga perubahan teks terdeteksi.
- `lexeme_text` memuat lema Strong's + token morfologi (`aorist`, `partisip`, `datif`, …) agar pertanyaan gramatikal bisa ditemukan lewat full-text.

### Hasil

| Metrik | Nilai |
|---|---|
| Chunk | **39** (1 per ayat) |
| Gagal | 0 |
| `token_est` | 95–297, rata-rata **186** |
| Kolom FTS terisi | 39 / 39 |
| `embedding` | **0** — menunggu Fase 6 |
| Pencarian `katakrima` | 1 chunk |
| Pencarian `aorist` | 17 chunk |
| Pencarian `penghukuman` | 1 chunk |
| Pencarian `κατακριμα` | 1 chunk |

### Wizard

*Konfigurasi → Jalankan Chunking* (`rag.chunking.wizard`), dengan opsi "hanya yang perlu diproses". Idempoten: chunk dicocokkan per (ayat, jenis unit).

---

## 11b. ⚠️ Batas waktu Odoo vs inferensi CPU

Kueri RAG memakan 40–170 detik di mesin ini. **Batas bawaan Odoo `limit_time_real` adalah 120 detik**, dan bila terlampaui Odoo akan membuang stacktrace lalu **reload diri sendiri** — bukan sekadar menggagalkan request.

Konfigurasi yang wajib ada di `/etc/odoo18.conf`:

```ini
limit_time_real = 600
limit_time_cpu = 300
```

Tanpa itu, kueri panjang bisa mematikan layanan. Unit `odoo18.service` juga sebaiknya memakai `Restart=on-failure` agar layanan tidak tertinggal mati.

**Log:** `/var/log/odoo` dimiliki user `odoo`, sedangkan layanan berjalan sebagai `odoo18`; logfile harus diarahkan ke direktori yang dapat ditulis (di sini `/var/log/odoo18/`), kalau tidak Odoo hanya menulis ke stdout dan berkas log tetap 0 byte.

---

## 12. Embedding otomatis (Fase 6)

| Komponen | Berkas | Catatan |
|---|---|---|
| Klien HTTP | `models/embedding_client.py` | timeout, 3× retry + backoff; galat 4xx tidak diulang |
| Antrean | `rag.chunk._cron_embed` | batch 16, commit per pemanggilan |
| Penjadwal | `data/rag_cron.xml` | `ir.actions.server` + `ir.cron`, tiap 5 menit |
| Tombol manual | `action_reembed` (chunk), `action_reembed_chunks` (ayat) | khusus RAG Manager |

Simpan vektor lewat SQL (`UPDATE ... SET embedding = %s::vector`) karena kolomnya tidak dikenal ORM.

### ⚠️ Odoo 18 menunda `write()`

Mencampur `write()` ORM dengan SQL mentah pada baris yang sama berbahaya: `write()` **tidak langsung** dieksekusi, sehingga bisa menimpa hasil `UPDATE` mentah. Kasus nyata di sini — status kembali `chunked` setelah embed. Karena itu `_embed()` memanggil `self.env.flush_all()` sebelum menulis vektor.

### Hasil

| Metrik | Nilai |
|---|---|
| Chunk ter-embed | **39 / 39** |
| Dimensi | 1024 |
| Durasi | 29 detik (batch 16) |
| Indeks | HNSW dipakai (`Index Scan`) |
| Galat | 0 |

### Kualitas pencarian semantik

5 dari 6 kueri uji tepat sasaran:

| Kueri | Top-1 | Cosine |
|---|---|---|
| tidak ada penghukuman | **8:1** | 0,659 |
| kemuliaan yang akan dinyatakan | **8:18** | 0,532 |
| Roh menolong kelemahan kita | **8:26** | 0,696 |
| tidak ada yang memisahkan dari kasih Allah | **8:39** | 0,585 |
| hidup menurut daging vs Roh | **8:5** | 0,678 |

Yang meleset: *"pengangkatan menjadi anak Allah"* → 8:14/8:17/8:19, bukan 8:23 (`υἱοθεσία`). Full-text menemukan 8:23, tetapi `plainto_tsquery` meng-AND semua kata. Ini bukti bahwa Fase 7 butuh `websearch_to_tsquery` atau OR, bukan hanya RRF.

---

## 13. Layanan Kueri (inti Fase 7)

`models/query_service.py` — `rag.query.service` dengan alur: **router → pencarian → context builder → LLM → log**.

| Tahap | Isi |
|---|---|
| Router | regex `Roma 8:N`/`8:N-M` → `direct`; selain itu `hybrid` |
| Pencarian | direct: ambil chunk ayat yang disebut. hybrid: dense + full-text, digabung **RRF k=60** |
| Tsquery | kata disaring stopword, digabung **OR**, lalu **diperluas** dengan sinonim teologis dari `rag.query.expansion` |
| Konteks | ayat terambil (rinci, bertanda ▶) + **perikop hit-1 disertakan utuh** (ayat lain ringkas) + morfologi + blok `[VARIAN TEKSTUAL]` + `[SUMBER]` |
| LLM | `POST /v1/chat/completions`, timeout dari konfigurasi |
| Audit | `rag.query.log` (pertanyaan, rute, latensi per tahap, token) + `rag.query.hit` (peringkat dense/fts, skor, RRF, apakah masuk konteks) |

### Dua cara menjalankan kueri

1. **Konsol** — *Kueri → Tanya RAG*, isi pertanyaan, tekan **Tanya**. Cara yang dianjurkan.
2. **Riwayat Kueri** — buat record, isi pertanyaan, lalu tekan **Jalankan Kueri** (header) atau ikon ▶ di list. Tombol hanya muncul saat status `draf` atau `galat`.

`rag.query.log` pada dasarnya adalah **tabel audit**; tombol di atas membuatnya bisa dipakai sebagai antrean kueri juga.

Status: `draf → berjalan → berhasil / galat`. Menjalankan ulang membersihkan hit lama sehingga tidak menggandakan `rag.query.hit`.

### Tab teks asli pada jawaban

Form riwayat kueri memakai notebook: **Jawaban** dan **Teks Asli (Yunani)**.

Field `greek_quotes` (terhitung) membaca ayat yang **dikutip di jawaban**, lalu menampilkan:

```
[Roma 8:30]  (konteks perikop)
Yunani     : οὓς δὲ προώρισεν, τούτους καὶ ἐκάλεσεν· ...
Translit   : ous de proōrisen toutous kai ekalesen ...
Tanpa aksen: ους δε προωρισεν τουτους και εκαλεσεν ...
```

Keterangan **hasil pencarian** vs **konteks perikop** membedakan ayat yang benar-benar terambil dari ayat yang masuk lewat perluasan perikop — mis. 8:30 pada kueri 27.

### Lima transaksi uji

| # | Pertanyaan | Rute | Latensi | Hit | Token (prompt/gen) |
|---|---|---|---|---|---|
| 13 | Roma 8:1 | direct | 40,0 s | 1 | 713 / 218 |
| 14 | Mengapa Paulus berkata tidak ada penghukuman… | hybrid | 120,8 s | 5 | 2.817 / 304 |
| 15 | Apa arti κατάκριμα dan bentuk gramatikalnya? | hybrid | 84,5 s | 5 | 2.630 / 97 |
| 16 | Perbedaan KJV dan AYT pada Roma 8:1 | direct | 42,2 s | 1 | 729 / 322 |
| 17 | Alur argumen dari penderitaan menuju kemuliaan | hybrid | 134,7 s | 5 | 2.323 / 480 |

Total **17 hit** (14 ayat unik). Rata-rata 84 detik per kueri — wajar untuk CPU tanpa GPU.

### Ekspansi kueri

Tabel `rag.query.expansion` memetakan istilah pertanyaan ke padanan yang ikut dicari. Contoh bawaan:

| Istilah | Padanan |
|---|---|
| keselamatan | diselamatkan, penebusan, dibenarkan, dimuliakan, dipanggil, ditetapkan, serupa |
| predestinasi | ditetapkan, dikenal, dipanggil, dibenarkan, dimuliakan |
| penghukuman | hukuman, katakrima, menghukum |

Dampaknya terukur: untuk pertanyaan "keselamatan", full-text yang semula **nol** hasil kini menemukan 5 chunk, dan **Roma 8:29 naik dari dense-20 ke RRF-3**. Padanan yang dipakai disimpan di `stage_ms['expanded']` untuk audit. Dikelola lewat *Konfigurasi → Ekspansi Kueri*.

### Mengapa ayat seperti 8:29–30 bisa tidak muncul

Pertanyaan generik ("pandangan Paulus mengenai keselamatan") menyebar ke seluruh pasal: 8:29 hanya peringkat 20 dari 39 pada pencarian vektor, 8:30 peringkat 35, dan full-text tidak menemukan satu kata pun karena "Paulus"/"keselamatan" tidak ada di Roma 8.

Perbaikannya dua lapis:

1. **Konteks perikop** — perikop dari hit peringkat 1 disertakan utuh, sehingga 8:28–30 ikut masuk meski tidak terambil. Diverifikasi: konteks memuat 8:29 dan 8:30 lengkap.
2. **Templat prompt v2** — memerintahkan menelusuri seluruh perikop, bukan hanya ayat bertanda ▶.

Setelah itu model menelusuri 8:18/23/24/26–27/35/37, tetapi **masih melewati 8:29–30** — batas kemampuan model 7B, bukan kegagalan retrieval.

Frasa yang menarik 8:29–30 dengan tepat: **"predestinasi"** (peringkat 1–2) atau menyebut **"Roma 8:28-30"** (rute *direct*, dijamin diambil).

### Tiga bug yang ditemukan saat menguji kueri

1. **`NameError`** pada rute direct — list hasil ditulis sebagai literal, bukan comprehension.
2. **Morfologi tidak masuk konteks** — jawaban soal `κατάκριμα` salah ("akusatif, partikel"). Setelah baris `Morf` ditambahkan: benar ("nomina, nominatif, tunggal, netral").
3. **`content_hash` tidak ter-update** saat teks diedit, sehingga pemeriksaan integritas menyatakan data utuh padahal tidak. Diubah menjadi computed stored.

> ⚠️ `action_reembed` memanggil `env.cr.commit()` internal. Di UI itu benar, tetapi di `odoo-bin shell` ia membuat `rollback` tidak berfungsi — pernah menyebabkan teks uji ikut tersimpan ke ayat 8:1.

---

## 14. Yang belum ada (memang di luar Fase 4)

- Wizard impor, normalisasi, chunking engine, parser apparatus → **Fase 5**
- Klien HTTP `/v1/embeddings`, `ir.cron`, tombol re-embed → **Fase 6**
- Query Router, RRF di Odoo, Context Builder, konsol tanya-jawab → **Fase 7**
- Uji install/upgrade menyeluruh & 10–15 pertanyaan evaluasi → **Fase 8**

Menu dan view dasar sudah ada agar data bisa diperiksa, tetapi UI lengkap baru dibangun di Fase 7.
