# PLAN.md — RAG Roma 8 (Odoo + PostgreSQL `pgvector` + `llama.cpp`)

> **Revisi 2 · 2026-11-21.**
> **R1** — rencana awal ditulis berdasarkan asumsi mesin 16 GB CPU-only yang belum diperiksa; audit langsung atas server membantah beberapa asumsi dan semuanya sudah dikoreksi.
> **R2** — sumber teks Roma 8 sudah ditemukan dan diuji unduh, serta skema data sudah dirancang dan diverifikasi di PostgreSQL 16. Tidak ada perubahan arah; yang ditambahkan adalah kepastian teknis.
> Perubahan ditandai **(R1)**/**(R2)** agar terlihat apa yang bergeser dari [PLAN-asli.md](docs/PLAN-asli.md).
> Jurnal: [PROGRESS.md](PROGRESS.md) · Papan centang: [STATUS.md](STATUS.md) · Daftar tugas: [TASK.md](TASK.md)

---

## 0. Ringkasan perubahan pada Revisi 1

| Aspek | Rencana awal | Kenyataan (terverifikasi) |
|---|---|---|
| Hardware | "16 GB RAM, CPU-only, anggaran AI 6–8 GB" | **i7-1260P 12C/16T, RAM 15,5 GB, swap 16 GB** — lebih kuat dari asumsi |
| PostgreSQL | belum disebut versinya | **16.15** (bukan 14/15) |
| `pgvector` | diasumsikan bisa langsung dipakai | **tidak terpasang**; harus diinstal, dan **tidak `trusted`** |
| Model LLM | "Qwen 3 8B atau Qwen 2.5 7B" | **Qwen2.5-7B-Instruct Q4_K_M** (terukur 8,3 tok/s), cadangan **Qwen3-4B** |
| Model embedding | "`bge-m3` atau `multilingual-e5-base`" | **`bge-m3` Q8_0, 1024 dim** — dikunci |
| Odoo | belum disebut lokasi | **18.2alpha1** (series 18.2) di `/opt/odoo18`, bukan 18.0 |
| Database | belum ditentukan | **`rag_roma8`** (owner `odoo18`), bukan DB produksi |
| Beban memori | "maksimal 6–8 GB, total < 85%" | **terukur 50,6%** total, AI ≈ 8,4 GB |
| Varian tekstual | "disorot otomatis oleh LLM" | **gagal pada uji pertama** — ternyata tersedia sebagai data apparatus, lihat §7 |
| Sumber teks (R2) | belum ditentukan | **RP2018** + **KJV** (keduanya public domain) siap; **LAI** butuh kunci API |
| Bahasa Indonesia (R2) | LAI/TB | **AYT** (CC, non-komersial) — dipakai sementara sampai kunci LAI diperoleh |
| Dataset Roma 8 (R2) | belum ada | **39 ayat lengkap**, 663 kata Yunani, 21 varian → `data/` |
| Data di Odoo (R2) | belum ada | **4 perikop, 39 ayat, 21 varian, 39 chunk** masuk `rag_roma8` |
| Dekoder morfologi (R2) | leksikon berlisensi | **146/146 kode** Robinson terurai ke Bahasa Indonesia, tanpa lisensi pihak ketiga |
| Skema data (R2) | belum dirancang | **17 tabel inti, 1 collection** (`rag_chunk`), DDL `tsvector`/HNSW **terverifikasi** di PG 16 |
| Modul Odoo (R2) | belum ada | **`rag_teologi` terpasang & teruji** di `rag_roma8` → [docs/MODUL-ODOO.md](docs/MODUL-ODOO.md) |

---

## 1. Tujuan & ruang lingkup

Membangun sistem *Retrieval-Augmented Generation* lokal yang terintegrasi penuh di backend **Odoo** untuk studi eksposisi dan perbandingan tekstual **Roma 8:1–39**. Tiga sumber disandingkan paralel per ayat:

- **Yunani Koine:** Robinson-Pierpont (*Byzantine Majority Textform*), dengan morfologi dan nomor Strong's.
- **Inggris:** King James Version (KJV).
- **Indonesia:** Lembaga Alkitab Indonesia (Terjemahan Baru).

Sistem harus mampu menjawab pertanyaan konseptual (hybrid search) **dan** pertanyaan varian tekstual (direct lookup), dengan sitasi ayat yang dapat diverifikasi.

---

## 2. Lingkungan terverifikasi (R1)

| Komponen | Nilai |
|---|---|
| Host | `192.168.18.222` · user `nms` · Ubuntu 24.04.5 LTS |
| CPU | Intel i7-1260P, **12 core / 16 thread** |
| RAM / Swap | 15,5 GB / 16 GB |
| Disk | 466 GB, **88% terpakai** (sisa 56 GB) |
| PostgreSQL | 16.15, cluster `main`, port 5432, `listen_addresses = *` |
| `pgvector` | 0.6.0 (paket Ubuntu, bukan 0.8.x) |
| `pg_trgm` | 1.6 |
| Odoo | **18.2alpha1** (series 18.2), `/opt/odoo18/odoo-bin`, service `odoo18.service`, port 8069 |
| `llama.cpp` | build **12032** (0.8.0-dev), `/home/nms/llama.cpp/build/bin/llama-server` |
| Database RAG | **`rag_roma8`**, owner `odoo18`, `vector` + `pg_trgm` aktif |

Catatan `pgvector` 0.6.0: tidak ada `halfvec`, `sparsevec`, maupun *iterative index scan*. Untuk korpus 39 ayat ini **tidak relevan**; HNSW 0.6.0 sudah memadai. Upgrade hanya jika nanti menangani korpus besar.

---

## 3. Arsitektur sistem (R1)

```
Odoo 18 (port 8069, user odoo18)
   │  ORM + SQL langsung (psycopg2)
   ▼
PostgreSQL 16.15 ──── db: rag_roma8 ──── vector 0.6.0 + pg_trgm 1.6
   ▲
   │  HTTP /v1/embeddings, /v1/chat/completions
   │
llama-embed  ←  bge-m3 Q8_0       127.0.0.1:8080   (1024 dim)
llama-chat   ←  Qwen2.5-7B Q4_K_M 127.0.0.1:8081   (ctx 8192, KV q8_0)
```

**Dua instance `llama-server` terpisah** — sesuai rencana awal, sekarang benar-benar berdiri sendiri sebagai unit systemd dan hanya listen di *loopback*.

| Unit | Port | Model | Threads | Status |
|---|---|---|---|---|
| `llama-embed.service` | 8080 | bge-m3 Q8_0 | 6 | enabled, active |
| `llama-chat.service` | 8081 | Qwen2.5-7B-Instruct Q4_K_M | 8 | enabled, active |
| `llama-chat-4b.service` | 8092 | Qwen3-4B Q4_K_M | 8 | disabled (cadangan) |
| `llama-server.service` | 7070 | router lama | — | tidak disentuh |

**Anggaran memori.** AI ≈ 8,4 GB (chat 7,7 GB + embed 0,77 GB); total sistem terukur **50,6%**, jauh di bawah batas 85%. Ini mengoreksi asumsi awal bahwa 6–8 GB adalah plafon keras — di mesin ini masih ada ruang, tetapi swap 16 GB tetap harus dijaga.

**Optimasi CPU-only yang dipertahankan:** RAG ketat parent-child (bukan full-context injection), context window 8192, KV cache `q8_0`, prompt caching aktif, thread = jumlah physical core, HTTP timeout klien 120–180 detik.

---

## 4. Pemilihan model (R1 — berbasis pengukuran)

Prompt uji 968 token, output 256 token, threads 8:

| Model | Prompt eval | Generasi | RSS | Catatan |
|---|---|---|---|---|
| **Qwen2.5-7B-Instruct Q4_K_M** | 37,4 tok/s | **8,3 tok/s** | 7.689 MB | **default** |
| **Qwen3-4B Q4_K_M** | 53,7 tok/s | **12,3 tok/s** | 4.765 MB | cadangan |

**Keputusan:** 7B sebagai default. 4B 48% lebih cepat, tetapi kualitas eksposisi Bahasa Indonesia dan kepatuhan *grounding* lebih menentukan untuk tugas ini. Jawaban 300 token selesai ±36 detik — masih di dalam batas timeout.

**Prompt caching terbukti aktif**: permintaan kedua dengan prompt identik hanya memproses 1 token (vs 968). Ini yang membuat RAG berulang dengan system prompt panjang layak dijalankan di CPU.

**Model embedding:** `bge-m3` Q8_0, **1024 dimensi** → mengunci skema `vector(1024)`. Latensi 0,07 s/teks (warm), batch 5 teks 0,24 s. Alternatif `multilingual-e5-base` (768 dim) **tidak dipakai** agar dimensi tidak berubah di tengah proyek.

---

## 5. Strategi data & chunking

- **Penyelarasan paralel (*verse-aligned*):** setiap ayat memuat teks Yunani berdiakritik, *stripped Greek*, KJV, LAI, dan anotasi morfologi/leksikon.
- **Child (unit pencarian):** 1 ayat. Embedding difokuskan pada LAI, KJV, dan transliterasi/lemma Yunani — karena model embedding multibahasa lemah pada Yunani politonik mentah.
- **Parent (unit konteks):** perikop utuh — 8:1–11 Hidup oleh Roh · 8:12–17 Anak-anak Allah · 8:18–30 Pengharapan Kemuliaan · 8:31–39 Keyakinan Iman.
- **Hybrid Search:** cosine similarity (`pgvector`) + full-text (`tsvector`) digabung dengan **Reciprocal Rank Fusion (RRF)**.
- **(R1) Penanda varian tekstual wajib.** Teks paralel saja tidak cukup — uji pertama menunjukkan LLM melewatkan klausa yang absen di LAI. Dataset harus menyimpan penanda eksplisit pada tingkat klausa, bukan hanya tiga kolom teks.
- **(R2) Sumber sudah pasti.** Yunani: `byztxt/byzantine-majority-text` — tiga varian berkas sekaligus menyediakan teks berdiakritik, teks tanpa aksen + parsing + Strong's, dan apparatus `{NA … > - }`. KJV: `ebible.org` VPL. LAI: API resmi, 39 ayat berada di bawah ambang izin non-komersial dengan atribusi wajib. Rincian: [docs/SUMBER-TEKS.md](docs/SUMBER-TEKS.md).
- **(R2) Ekspansi kueri.** Pertanyaan generik seperti "keselamatan" diperluas ke sinonim teologis (dimuliakan, dibenarkan, dipanggil), sehingga ayat seperti Roma 8:29–30 tetap terjangkau walau kedekatan vektornya rendah.
- **(R2) Varian tidak lagi hasil inferensi.** Apparatus RP menandai sendiri bahwa NA menghilangkan klausa 8:1b, sehingga varian dapat diurai saat impor menjadi tabel data, bukan disimpulkan model.
- **(R2) Dataset sudah terwujud.** `data/roma8.json` memuat 39 ayat paralel (Yunani berdiakritik, tanpa aksen, transliterasi, KJV, AYT), 663 kata dengan Strong's + parsing, 21 varian, dan pemetaan 4 perikop. Rincian: [data/README.md](data/README.md).

---

## 6. Arsitektur modul Odoo

Modul kustom bertindak sebagai *self-contained RAG engine*, tanpa orchestrator eksternal. Skema lengkap 17 tabel inti, kolom vektor/tsvector, dan query RRF: **[docs/DESAIN-SKEMA.md](docs/DESAIN-SKEMA.md)**.

- **Master Konfigurasi LLM & RAG:** endpoint `llama-server`, parameter model, `top-k`, timeout, templat system prompt.
- **Master Perikop (parent) & Master Ayat (child):** relasi `Many2one` untuk seluruh entitas referensi (kitab, perikop, tema, kategori bahasa). `Selection` **hanya** untuk status: `draft`, `chunked`, `embedded`, `error`.
- **Model Chunk & Vektor:** menyimpan hasil chunking, *stripped Greek*, kolom `tsvector`, dan kolom `vector` yang dibuat via SQL hook.
- **Model Riwayat Kueri:** pertanyaan, ayat terambil, skor retrieval, latensi, respons LLM.
- **Otomatisasi embedding:** `ir.cron` batch untuk record `chunked` atau *dirty*, agar worker HTTP Odoo tidak terblokir.
- **Keamanan:** **RAG User** (kueri + riwayat sendiri) vs **RAG Manager** (master data, impor, re-embed) via `ir.model.access.csv` dan `ir.rule`.

### (R1) Kendala teknis yang harus diakomodasi

1. **Ekstensi `vector` tidak `trusted`.** Hanya superuser bisa `CREATE EXTENSION`. Solusi terpilih: ekstensi dibuat sekali sebagai `postgres` di DB target; hook modul memakai `CREATE EXTENSION IF NOT EXISTS` yang **terbukti aman** dijalankan user `odoo18` ketika ekstensi sudah ada. Untuk DB baru, langkah ini wajib diulang.
2. **`addons_path` hanya `/opt/odoo18/addons`** dan dimiliki root. Modul harus dideploy via sudo, atau tambahkan path baru di `/etc/odoo18.conf`.
3. **PostgreSQL 16.15**, bukan 14 — path instalasi dan nama paket mengikuti 16 (`postgresql-16-pgvector`).

---

## 7. Strategi prompting, guardrails & evaluasi

- **Strict grounding:** jawab hanya dari konteks; temperature 0,1–0,3.
- **Sitasi wajib:** nomor ayat + kutipan kata persis.
- **(R1) Varian tekstual tidak boleh diserahkan pada inferensi LLM.** Uji pertama gagal: model menyebut `κατάκριμα` dengan benar tetapi melewatkan bahwa klausa `μὴ κατὰ σάρκα περιπατοῦσιν ἀλλὰ κατὰ πνεῦμα` ada di RP/KJV dan tidak ada di LAI, lalu mengarang perbedaan pada kata yang justru sama. Penanganan yang direncanakan:
  1. *Context Builder* menyertakan penanda eksplisit, mis. `[klausa tidak ada di LAI]` — bukan sekadar tiga teks berdampingan.
  2. *System prompt* memerintahkan membandingkan **kehadiran klausa**, bukan hanya pilihan kata.
  3. Pertanyaan varian dirutekan ke jalur `direct lookup` yang menyajikan metadata varian, tidak diserahkan ke LLM.
- **Evaluasi:** *retrieval accuracy*, fidelitas kutipan Yunani/KJV/LAI, stabilitas RAM/CPU, dan latensi.

---

## 8. Rencana per fase

| Fase | Isi | Status |
|---|---|---|
| **1** | Akuisisi & kurasi data Roma 8:1–39 (RP+KJV+AYT, alignment, perikop) | ✅ **selesai** — 39 ayat, verifikasi lulus → [data/README.md](data/README.md) |
| **2** | Infrastruktur `llama.cpp` & benchmark CPU | ✅ selesai |
| **3** | PostgreSQL: `pgvector`, `pg_trgm`, dimensi 1024 | ✅ selesai — indeks HNSW/GIN **terpasang** |
| **4** | Modul Odoo: model, SQL hook, hak akses | ✅ **selesai** — `rag_teologi` terpasang & teruji → [docs/MODUL-ODOO.md](docs/MODUL-ODOO.md) |
| **5** | Ingestion, normalisasi, chunking, dirty flag | ✅ **selesai** — 39 ayat, 21 varian, 39 chunk, `embed_text` terisi |
| **6** | Embedding otomatis (`ir.cron`, klien HTTP, re-embed) | ✅ **selesai** — 39 vektor 1024 dim |
| **7** | Query Router, Hybrid RRF, Context Builder, UI | 🟡 hampir selesai: router, RRF, konteks, ekspansi kueri, prompt v2, konsol, teks asli, pilihan konfigurasi |
| **8** | Uji end-to-end & evaluasi | ⬜ belum (uji per komponen sudah berjalan) |

Rincian centang ada di [STATUS.md](STATUS.md); riwayat kronologis di [PROGRESS.md](PROGRESS.md).

---

## 9. Risiko & keputusan tertunda

| # | Risiko / keputusan | Dampak | Status |
|---|---|---|---|
| 1 | `shared_buffers` hanya **128 MB** | HNSW & RRF lambat; perlu 1–2 GB | ⏳ butuh restart PostgreSQL |
| 2 | Sumber teks LAI/TB berhak cipta | **Ditembus sementara dengan AYT** (CC, non-komersial, atribusi wajib). Bila nanti dipakai TB, kunci API tetap perlu | ⏳ pengajuan ke `info@alkitab.or.id`; kolom `ind` bisa diganti tanpa ubah struktur |
| 3 | Disk 88% terpakai (sisa 56 GB) | Cukup untuk proyek ini, tapi memantau | 👁 dipantau |
| 4 | `listen_addresses = *` pada 5432 | PostgreSQL terbuka ke LAN | ⏳ usul: `localhost` |
| 5 | API key `llama-server` 7070 di argv | Bocor lewat `ps` | ⏳ di luar lingkup modul |
| 6 | `pgvector` 0.6.0 (bukan 0.8.x) | Tidak ada `halfvec`/`sparsevec` | ✅ diterima, tidak relevan |
| 7 | Kualitas varian tekstual | Jawaban bisa menyesatkan | 🔧 mitigasi di §7 + tabel `rag_variant` |
| 8 | Leksikon (Thayer/Abbott-Smith) | Belum diputuskan; tidak menghambat | ⏸ ditunda — Strong's + parsing sudah cukup; tabel terpisah, tanpa ubah skema |
| 9 | Modul harus ditulis ke `/opt/odoo18/addons` (milik root) | Deploy butuh sudo tiap iterasi | ✅ ditangani `scripts/deploy_module.sh` |
| 10 | Inferensi CPU 40–170 detik vs `limit_time_real` bawaan 120 detik | Odoo reload diri lalu mati | ✅ limit 600/300 + `Restart=on-failure` |
| 11 | Log Odoo tidak dapat ditulis (`/var/log/odoo` milik user lain) | Berkas log 0 byte | ✅ dipindah ke `/var/log/odoo18/` |

---

## 10. Referensi

- [TASK.md](TASK.md) — daftar tugas revisi (R2)
- [docs/PLAN-asli.md](docs/PLAN-asli.md) — rencana awal, tanpa perubahan
- [docs/TASK-asli.md](docs/TASK-asli.md) — daftar tugas awal
- [docs/EVALUASI-postgresql.md](docs/EVALUASI-postgresql.md) — audit PostgreSQL & instalasi pgvector
- [docs/BENCHMARK-LLAMA.md](docs/BENCHMARK-LLAMA.md) — benchmark & konfigurasi layanan
- [docs/SUMBER-TEKS.md](docs/SUMBER-TEKS.md) — sumber teks RP, KJV, LAI (terverifikasi)
- [docs/DESAIN-SKEMA.md](docs/DESAIN-SKEMA.md) — desain collection & struktur field
- [docs/MODUL-ODOO.md](docs/MODUL-ODOO.md) — modul `rag_teologi`: struktur, deploy, hasil uji
- [STATUS.md](STATUS.md) — papan centang
- [PROGRESS.md](PROGRESS.md) — jurnal
