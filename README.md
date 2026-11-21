# RAG Roma 8 — Odoo + PostgreSQL `pgvector` + `llama.cpp`

![License: LGPL-3](https://img.shields.io/badge/license-LGPL--3-blue)
![Odoo](https://img.shields.io/badge/Odoo-18.2-875A7B)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791)
![pgvector](https://img.shields.io/badge/pgvector-0.6.0-orange)
![llama.cpp](https://img.shields.io/badge/llama.cpp-CPU--only-lightgrey)
![Python](https://img.shields.io/badge/python-3.12-3776AB)
![Status](https://img.shields.io/badge/status-beta-yellow)

Sistem **Retrieval-Augmented Generation lokal** untuk studi eksposisi dan perbandingan tekstual **Roma 8:1–39**, berjalan sepenuhnya di dalam **Odoo** tanpa *orchestrator* eksternal — tanpa GPU, tanpa layanan cloud.

Tiap ayat disandingkan paralel dalam tiga bahasa: **Yunani Koine** (Robinson-Pierpont 2018, Byzantine Textform), **Inggris** (KJV 1769), dan **Indonesia** (AYT).

---

## ✨ Fitur

| Fitur | Keterangan |
|---|---|
| **Tiga sumber paralel** | Yunani berdiakritik, tanpa aksen, transliterasi, KJV, AYT — terselaras per ayat |
| **Morfologi lengkap** | 663 kata Yunani dengan nomor Strong's + parsing Robinson, diterjemahkan ke Bahasa Indonesia (146/146 kode) |
| **Varian tekstual sebagai data** | 21 varian diurai dari apparatus RP, bukan disimpulkan LLM — termasuk klausa Roma 8:1 yang dihilangkan NA |
| **Hybrid search** | Cosine (`pgvector`/HNSW) + full-text (`tsvector`/GIN) digabung dengan **Reciprocal Rank Fusion** |
| **Ekspansi kueri** | 12 istilah sinonim teologis; "keselamatan" ikut mencari *dimuliakan, dibenarkan, dipanggil* |
| **Konteks berlapis** | Ayat terambil (rinci) + perikopnya (ringkas) agar alur argumen Paulus tidak terputus |
| **Audit penuh** | Setiap kueri menyimpan rute, peringkat dense/fts, skor RRF, token, latensi per tahap |
| **Teks asli di UI** | Tab *Teks Asli (Yunani)* mengikuti ayat yang benar-benar dikutip jawaban |
| **CPU-only** | 2 instance `llama.cpp` (chat + embedding), context 8192, KV cache `q8_0`, prompt caching |
| **Idempoten** | Impor, chunking, embedding, dan DDL modul semuanya aman dijalankan berulang |

---

## 🏗 Arsitektur

```
                    ┌──────────────────────────────────────┐
   Peramban  ──────▶│  Odoo 18.2  (modul rag_teologi)      │
                    │  Router · RRF · Context Builder      │
                    └───────┬──────────────────────┬───────┘
                            │ ORM + SQL            │ HTTP
                            ▼                      ▼
              ┌──────────────────────┐   ┌────────────────────┐
              │ PostgreSQL 16.15     │   │ llama-chat :8081   │
              │  pgvector 0.6 (HNSW) │   │ Qwen2.5-7B Q4_K_M  │
              │  tsvector (GIN)      │   └────────────────────┘
              │  pg_trgm             │   ┌────────────────────┐
              │  db: rag_roma8       │   │ llama-embed :8080  │
              └──────────────────────┘   │ bge-m3 Q8_0 (1024) │
                                         └────────────────────┘
```

Satu **collection** pencarian: tabel `rag_chunk` (vektor + 3 kolom `tsvector`). Perikop, varian, dan ekspansi adalah konteks yang di-*join*, bukan target pencarian vektor.

---

## 📁 Struktur repositori

```
module/rag_teologi/       Modul Odoo: 17 model inti + 3 wizard, 25 view, 36 ACL
  models/                 morph.py (dekoder Robinson), chunker.py, query_service.py
  wizard/                 impor dataset, chunking, konsol tanya-jawab
  views/                  menu, form, list, konsol
  security/               RAG User / RAG Manager + record rule
  data/                   seed master + glos Strong's (5.624 entri)
scripts/
  fase1_build.py          bangun dataset Roma 8 dari tiga sumber
  build_strongs_gloss.py  Strong's .dat → JSON
  deploy_module.sh        unggah + install/upgrade + restart
  bench_llama.py          benchmark prompt eval & token/detik
  rrun.py                 helper SSH/SFTP
data/                     dataset terkurasi + laporan verifikasi
docs/                     evaluasi PostgreSQL, benchmark, desain skema, modul, sumber teks
deploy/                   unit systemd untuk llama-server
```

---

## ⚙️ Prasyarat

- **Odoo 18.2** (diuji pada `18.2alpha1`) + Python 3.12
- **PostgreSQL 16** dengan ekstensi `vector` (pgvector ≥ 0.5) dan `pg_trgm`
- **llama.cpp** (build ≥ 12032) + GGUF:
  - `bge-m3-Q8_0` — embedding, 1024 dimensi
  - `Qwen2.5-7B-Instruct-Q4_K_M` — chat (atau `Qwen3-4B` untuk mesin lebih lemah)
- RAM ≥ 12 GB, tanpa GPU (diuji pada i7-1260P, 15,5 GB)

---

## 🚀 Instalasi

```bash
# 1. Database
sudo -u postgres createdb -O <odoo-user> rag_roma8
sudo -u postgres psql -d rag_roma8 -c "CREATE EXTENSION vector; CREATE EXTENSION pg_trgm;"

# 2. Layanan llama.cpp (sesuaikan path model)
sudo cp deploy/llama-embed.service deploy/llama-chat.service /etc/systemd/system/
sudo systemctl enable --now llama-embed llama-chat

# 3. Modul Odoo
cp -r module/rag_teologi /opt/odoo18/addons/
sudo -u odoo18 /opt/odoo18/venv/bin/python3 /opt/odoo18/odoo-bin \
  -c /etc/odoo18.conf -d rag_roma8 -i rag_teologi --stop-after-init --no-http

# 4. Dataset (opsional: bangun ulang dari sumber)
python3 scripts/build_strongs_gloss.py
sudo mkdir -p /opt/odoo18/rag-data && sudo cp data/roma8.json /opt/odoo18/rag-data/
```

Setelah modul terpasang, jalankan dari UI **RAG Teologi**:

1. *Konfigurasi → Impor Dataset…* → 4 perikop, 39 ayat, 21 varian
2. *Konfigurasi → Jalankan Chunking* → 39 chunk + `embed_text`
3. *Konfigurasi → Pengaturan RAG* → cek endpoint; embedding jalan otomatis tiap 5 menit (atau tombol **Re-embed**)
4. *Kueri → Tanya RAG* → ajukan pertanyaan

### ⚠️ Konfigurasi wajib

```ini
# /etc/odoo18.conf — inferensi CPU 40–170 detik, jauh di atas default 120 detik
limit_time_real = 600
limit_time_cpu = 300
```

Tanpa ini, kueri panjang akan melewati batas worker Odoo, memicu **reload server**, dan berpotensi mematikan layanan. Unit `odoo18.service` sebaiknya memakai `Restart=on-failure`.

---

## 🗄 Skema ringkas

| Tabel | Peran |
|---|---|
| `rag_book`, `rag_pericope`, `rag_verse` | master kitab / perikop (parent) / ayat (child) |
| `rag_chunk` | **collection**: `embedding vector(1024)` + `fts_id`/`fts_en`/`fts_gr` |
| `rag_variant` | varian tekstual (saksi, jenis, bacaan Byzantine vs lainnya) |
| `rag_config`, `rag_embedding_model`, `rag_prompt_template` | konfigurasi & preset |
| `rag_query_expansion` | sinonim teologis untuk ekspansi kueri |
| `rag_query_log`, `rag_query_hit` | audit kueri & peringkat ayat |
| `rag_import_batch` | jejak impor |

Rincian lengkap: [`docs/DESAIN-SKEMA.md`](docs/DESAIN-SKEMA.md).

---

## 📊 Hasil terukur

| Metrik | Nilai |
|---|---|
| Embedding 39 chunk | 29 detik (bge-m3, CPU) |
| Kemiripan cosine ke vektor sendiri | `1.0000` |
| Token `embed_text` per ayat | 95–297 (rata-rata 186) |
| Chat 7B | 8,3 token/detik · 4B: 12,3 token/detik |
| prompt caching | permintaan berulang hanya memproses **1 token** prompt |
| Uji semantik (6 kueri) | 5 tepat sasaran tanpa ekspansi; 8:29 naik ke RRF-3 dengan ekspansi |

---

## 📜 Lisensi & atribusi

| Komponen | Lisensi |
|---|---|
| Kode modul & skrip | **LGPL-3** |
| Robinson-Pierpont 2018 (Yunani) | Public Domain |
| King James Version 1769 | Public Domain (di luar Inggris) |
| **AYT — Alkitab Yang Terbuka** | © 2011–2024 YLSA-AYT, **non-komersial** |
| Strong's Greek Dictionary | Public Domain (Open Scriptures) |

**Catatan AYT:** teks Indonesia di dataset ini memakai AYT, bukan TB/LAI. AYT berlisensi non-komersial dengan atribusi; bila Anda memakai proyek ini secara komersial, ganti teks Indonesia sesuai lisensi Anda sendiri. AYT bukan TB: 8:1 AYT *"Karena itu, sekarang tidak ada lagi penghukuman…"* vs TB *"Demikianlah sekarang tidak ada penghukuman…"*.

---

## ⚠️ Keterbatasan yang diketahui

1. **Model 7B bisa melewatkan ayat konteks** yang tidak ditandai hasil pencarian, meski ayat itu ada di prompt. Mitigasi: ekspansi kueri, atau sebut nomor ayat (rute *direct*).
2. **Pertanyaan generik menyebar** — "keselamatan" tanpa ekspansi menempatkan 8:29 di peringkat 20 dari 39.
3. **pgvector 0.6.0** belum mendukung `halfvec`/`sparsevec`; tidak relevan untuk 39 ayat.
4. **Latensi** 40–170 detik per kueri di CPU tanpa GPU.
5. Varian tekstual hanya dari apparatus RP (NA/ECM), belum semua saksi.

---

## 🏷 Topik

`odoo` · `odoo18` · `rag` · `retrieval-augmented-generation` · `pgvector` · `postgresql` · `llama-cpp` · `hybrid-search` · `reciprocal-rank-fusion` · `embeddings` · `bge-m3` · `cpu-inference` · `bible` · `exegesis` · `theology` · `greek` · `byzantine-text` · `robinson-pierpont` · `kjv` · `indonesian`

---

<p align="center"><sub>Dibangun untuk studi eksposisi yang dapat diaudit: setiap klaim harus punya ayat, dan setiap ayat punya teks aslinya.</sub></p>
