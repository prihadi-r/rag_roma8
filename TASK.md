# TASK.md — Implementasi RAG Roma 8 (Odoo + PostgreSQL `pgvector` + `llama.cpp`)

> **Revisi 2 · 2026-11-21.** Turunan dari [docs/TASK-asli.md](docs/TASK-asli.md).
> Tugas ditandai `[x]` bila sudah **diverifikasi**, bukan sekadar dikerjakan. Tambahan yang tidak ada di daftar awal ditandai **(R2)**.
> Konteks & keputusan: [PLAN.md](PLAN.md) · Jurnal: [PROGRESS.md](PROGRESS.md) · Papan centang: [STATUS.md](STATUS.md)

---

## Fase 0 — Fondasi & Audit **(R2, tidak ada di daftar awal)**

- [x] Akses SSH ke `192.168.18.222` (`nms`), sudo via stdin
- [x] Audit CPU/RAM/disk/OS server target
- [x] Audit PostgreSQL: versi, cluster, database, tuning, `pg_hba`
- [x] Identifikasi penyebab swap thrashing (model 20B) dan mengatasinya
- [x] Arsipkan `PLAN.md` & `TASK.md` asli ke `docs/`

---

## Fase 1 — Akuisisi & Kurasi Data

- [x] **(R2)** Verifikasi sumber Robinson-Pierpont: `byztxt/byzantine-majority-text` (public domain) — `ROM.csv` berdiakritik, tanpa aksen + parsing + Strong's, dan apparatus
- [x] **(R2)** Verifikasi sumber KJV: `ebible.org/Scriptures/eng-kjv_vpl.zip` (public domain)
- [x] **(R2)** Keputusan Indonesia: pakai **AYT** (CC, non-komersial) — LAI tetap diajukan, belum diperoleh
- [x] Ekstrak Roma 8:1–39 dari RP (3 varian berkas), KJV, dan AYT → `data/roma8.json`
- [x] Kumpulkan teks Indonesia Roma 8:1–39 (AYT) + atribusi `AYT © 2011–2024 YLSA-AYT`
- [ ] Ganti ke TB/LAI bila kunci API diperoleh (tanpa ubah struktur dataset)
- [x] Bersihkan teks: UTF-8 konsisten, kurung sisipan KJV dipisah (`kjv` vs `kjv_raw`), `¶` jadi metadata
- [x] Urai apparatus RP menjadi data varian tingkat klausa → **21 varian** (18 substitusi, 3 omit)
- [x] Alignment 1-ke-1 untuk ke-39 ayat, verifikasi kelengkapan (**lulus**: 39 ayat di 4 sumber, jumlah kata cocok di tiap ayat)
- [x] Tentukan batas perikop 8:1–11, 8:12–17, 8:18–30, 8:31–39 (dikonfirmasi penanda `¶`)
- [x] Siapkan daftar istilah teologis kunci per ayat → `data/istilah-kunci.csv` (27 istilah)

**Status:** Fase 1 selesai dengan AYT. Sisa: penggantian ke TB/LAI bila kunci diperoleh.

---

## Fase 2 — Setup Infrastruktur Lokal & Benchmark CPU

- [x] `llama-server` chat: ctx 8192, KV cache `q8_0`, prompt caching aktif, threads = 8 (`127.0.0.1:8081`)
- [x] `llama-server` embedding: `bge-m3` `Q8_0`, 1024 dim (`127.0.0.1:8080`)
- [x] Benchmark 4B vs 7B pada mesin target → 7B **8,3 tok/s**, 4B **12,3 tok/s**
- [x] Uji beban memori gabungan (Odoo + PG + Zabbix + 2 llama) → **50,6%**, swap dari tumpukan RAG hanya 169 MB
- [x] **(R2)** Verifikasi prompt caching: permintaan berulang hanya memproses 1 token prompt
- [x] **(R2)** Layanan dijadikan unit systemd (enabled, restart-on-failure), bind loopback saja
- [x] **(R2)** Model cadangan 4B tersedia sebagai unit `disabled`

---

## Fase 3 — Setup PostgreSQL (`pgvector` & Full-Text Search)

- [x] Instal & aktifkan `pgvector` (0.6.0) dan `pg_trgm` (1.6)
- [x] Kunci dimensi kolom vektor: **1024** untuk `bge-m3`
- [x] **(R2)** Buat database khusus `rag_roma8` (owner `odoo18`) — bukan DB produksi
- [x] **(R2)** Verifikasi `CREATE EXTENSION IF NOT EXISTS vector` aman dijalankan user `odoo18`
- [x] **(R2)** Rancang skema indeks HNSW + 3× GIN `tsvector` + GIN trigram
- [ ] Terapkan indeks pada tabel nyata (menunggu modul Fase 4)
- [ ] Tuning `shared_buffers` 128 MB → 1–2 GB *(butuh restart PostgreSQL)*

---

## Fase 4 — Inisialisasi Custom Module Odoo & Skema Data

- [x] **(R2)** Desain skema lengkap: 17 tabel inti, 1 collection (`rag_chunk`), 4 kolom non-ORM → [docs/DESAIN-SKEMA.md](docs/DESAIN-SKEMA.md)
- [x] **(R2)** Verifikasi DDL: `tsvector GENERATED` (Yunani ikut terindeks), HNSW, query RRF, trigger dirty flag
- [x] Struktur modul `rag_teologi` + manifest (dependensi `base`), terpasang di `/opt/odoo18/addons`
- [x] 15 model: konfigurasi, perikop (parent), ayat (child), chunk/vektor, riwayat kueri, varian, impor
- [x] Aturan arsitektur dipatuhi: `Many2one` untuk referensi, `Selection` hanya untuk `state`
- [x] SQL hook: `vector(1024)` + 3 `tsvector` generated + HNSW/GIN/trigram, idempoten pada install & upgrade
- [x] Hak akses **RAG User** & **RAG Manager**: 29 baris ACL + 4 record rule
- [x] **(R2)** Prosedur deploy otomatis: `scripts/deploy_module.sh` (sintaks → unggah → addons → upgrade → restart)

---

## Fase 5 — Ingestion, Normalisasi & Chunking Engine

- [x] Wizard impor di backend Odoo (`rag.import.wizard`) — berkas JSON atau path server, idempoten
- [ ] Normalisasi teks otomatis saat impor → kolom *stripped Greek*
- [x] Decoder parsing code (`models/morph.py`): **146/146 kode** di Roma 8 terurai, teruji di luar Odoo
- [ ] **(R2)** Parser apparatus RP `{NA … > - }` → baris `rag_variant`
- [x] Chunking Engine (`models/chunker.py`): **39 chunk** dibuat, 0 gagal, terhubung ke perikop
- [x] Komposisi `embed_text` (ID/EN/Yunani/transliterasi/lema/glos) + `embed_hash` + `token_est`
- [x] *Dirty flag* otomatis: edit teks ayat → ayat & chunk terkait ditandai kotor

---

**Status:** **selesai penuh** — 4 perikop, 39 ayat, 21 varian, 39 chunk. Vektor belum diisi (Fase 6).

---

## Fase 6 — Otomatisasi Embedding (`ir.cron`)

- [x] Klien HTTP `models/embedding_client.py`: timeout, 3× retry dengan backoff, galat 4xx tidak diulang
- [x] `ir.cron` **RAG: Embedding Chunk** (tiap 5 menit), batch 16 → simpan vektor → `embedded`
- [x] Tombol *Re-embed* pada List & Form chunk, dan *Re-embed Chunk* pada form ayat (RAG Manager)
- [x] **(R2)** `retry_count` + `last_error` + status `error` setelah 3 kegagalan

---

## Fase 7 — Pemrosesan RAG & Antarmuka Pengguna Odoo

- [x] Query Router: regex `Roma 8:N`/`8:N-M` → **direct**, selain itu → **hybrid**
- [x] Hybrid Search SQL: dense + `tsvector` dengan **RRF (k=60)**, tsquery dibangun dari OR kata (bukan AND)
- [x] Context Builder: perikop + Yunani/KJV/AYT + **morfologi** + blok varian + label sumber
- [x] Perluasan konteks: perikop hit-1 disertakan utuh (menutup celah 8:29–30)
- [x] Templat prompt v2: telusuri seluruh perikop, bukan hanya ayat bertanda
- [x] Ekspansi kueri: tabel sinonim teologis (`rag.query.expansion`) + 12 istilah awal
- [x] Tab **Teks Asli (Yunani)** pada jawaban — mengikuti ayat yang dikutip, dengan penanda asal
- [x] Pilihan **Pengaturan RAG** per kueri di konsol + pengaman model embedding
- [x] Beberapa konfigurasi aktif sekaligus (preset) — indeks unik tunggal dihapus
- [x] Panggilan `/v1/chat/completions` dengan timeout dari konfigurasi (180 detik)
- [x] Konsol **Tanya RAG** (`rag.query.wizard`) + menu Kueri
- [x] Tombol **Jalankan Kueri** pada Riwayat Kueri (state draft/berjalan)
- [ ] Search view & penyempurnaan UI
- [ ] (Opsional) Ekspos layanan RAG via REST/JSON-RPC

---

## Operasional & pemulihan **(R2)**

- [x] `limit_time_real = 600`, `limit_time_cpu = 300` (inferensi CPU > 120 detik)
- [x] `Restart=on-failure` + `RestartSec=5` pada `odoo18.service`
- [x] Log layanan ke `/var/log/odoo18/odoo18.log` (sebelumnya tidak dapat ditulis)
- [ ] Pantau: kueri > 150 detik masih berisiko bila konteks membesar

---

## Fase 8 — Pengujian End-to-End & Evaluasi

- [ ] Uji install & upgrade modul (tidak ada konflik ORM vs kolom `pgvector`)
- [ ] Uji Wizard impor, Chunking, dan `ir.cron` untuk 39 ayat (termasuk re-embedding parsial)
- [ ] Buat 10–15 pertanyaan uji: kata Yunani, KJV vs LAI, varian 8:1, alur argumen Paulus
- [ ] Evaluasi: akurasi ayat terambil, fidelitas kutipan, waktu respons CPU
- [ ] Penyetelan akhir bobot RRF atau system prompt
- [ ] **(R2)** Uji regresi khusus varian: pertanyaan 8:1 **wajib** menyebut klausa yang dihilangkan NA

---

## Tugas yang ditunda (bukan bagian MVP)

- [ ] Tabel leksikon (Abbott-Smith/Thayer) — ditambahkan sebagai tabel terpisah via Strong's, tanpa ubah skema inti
- [ ] Tabel tema teologis per ayat
- [ ] Embedding tingkat perikop (cukup tambah baris `rag_chunk`, bukan tabel baru)
- [ ] Upgrade `pgvector` ke 0.8.x bila butuh `halfvec`/`sparsevec`
