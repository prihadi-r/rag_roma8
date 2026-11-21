# PROGRESS.md — Jurnal Pekerjaan RAG Roma 8

**Sesi 1** · 2026-11-21 · server `192.168.18.222` (`nms`)

> Jurnal berbasis butir. Papan centang: [STATUS.md](STATUS.md) · Rencana revisi: [PLAN.md](PLAN.md) · Rencana awal (arsip): [docs/PLAN-asli.md](docs/PLAN-asli.md)

---

## 1. Pembacaan rencana

- Membaca `TASK.md` dan `PLAN.md` sebelum menyentuh sistem.
- Lingkup yang dipahami: RAG Roma 8:1–39 di dalam Odoo, tiga sumber paralel (Robinson-Pierpont / KJV / LAI), `pgvector` + `tsvector` + `pg_trgm`, dua instance `llama-server`, struktur parent-child, RRF, delapan fase kerja.
- Kecurigaan awal: PLAN mengasumsikan "16 GB RAM, CPU-only, anggaran AI 6–8 GB" tanpa pernah memeriksa mesin target.

## 2. Audit mesin lokal (bukan target)

- Diperiksa sebelum pengguna mengarahkan ke server: laptop `i5-3320M` (2 core/4 thread), PostgreSQL **14.24**, Odoo 18, `llama-server` ada.
- Ditemukan **`pgvector` tidak tersedia** dan tidak ada berkas `.gguf`.
- Audit ini tidak dipakai lebih lanjut; nilainya hanya menyadari bahwa `pgvector` belum tentu terpasang.

## 3. Jalur SSH berpassword

- Login memakai password; `sshpass`, `expect`, dan akses `sudo` lokal tidak tersedia.
- Dibuat [scripts/rrun.py](scripts/rrun.py) berbasis **paramiko** (tersedia di sistem), membaca password dari berkas mode 0600 — bukan argumen, agar tidak tampak di daftar proses.
- Ditambahkan mode `--sudo` yang mengirim password lewat **stdin** (`sudo -S -p ''`), juga agar tidak terlihat di `ps` remote.
- Penempatan kredensial mengalami dua kegagalan: `~/.rsh_pass` ditolak (`Read-only file system`), dan `/tmp` ternyata **privat per perintah** sehingga berkas tidak terlihat pada pemanggilan berikutnya.
- Solusi akhir: `.secrets/rsh_pass` di dalam workspace, mode 0600, masuk `.gitignore`.
- Login berhasil; `nms` anggota grup `sudo`, `docker`, dan `ollama`.

## 4. Audit server target

- OS Ubuntu 24.04.5 LTS; CPU **i7-1260P 12 core / 16 thread**; RAM 15,5 GB; swap 16 GB.
- PostgreSQL **16.15**, cluster `main`, port 5432 — bukan versi 14 seperti dugaan awal.
- **`pgvector` tidak terpasang**; kandidat apt `postgresql-16-pgvector 0.6.0-1`.
- Sudah berjalan: Odoo 18 (`:8069`), ollama (`:11434`), dua proses `llama-server`.
- Temuan mengejutkan: RAM `used` 8,4 GB dan swap 10 GB sudah terpakai sebelum pekerjaan ini dimulai.

## 5. Instalasi pgvector

- `apt-get update && apt-get install -y postgresql-16-pgvector` lewat `rrun.py --sudo`.
- Terpasang `postgresql-16-pgvector 0.6.0-1`.
- Verifikasi di database scratch `rag_ext_test` (dibuat, diuji, dihapus): `vector 0.6.0` + `pg_trgm 1.6` aktif.
- `CREATE INDEX ... USING hnsw (emb vector_cosine_ops)` berhasil; `USING gin (txt)` berhasil.
- `EXPLAIN` membuktikan HNSW benar-benar dipakai: `Index Scan using t_emb_idx` dengan `Order By: (emb <=> ...)`.
- Sempat tampak bug: `cosine_sim` dua vektor berbeda (0.1 vs 0.2) sama-sama 1.000 — ternyata benar, cosine tidak peka skala.

## 6. Evaluasi mendalam PostgreSQL

- Database: `zabbix` 1,3 GB, `demo` 81 MB, `odoo18` 48 MB.
- `shared_buffers` hanya **128 MB**; `work_mem` 4 MB; `listen_addresses = *` (terbuka ke LAN).
- `vector.control` **tidak memiliki `trusted = true`** → `CREATE EXTENSION` hanya bisa superuser.
- Akar masalah swap ditemukan: `llama-server` memuat **gpt-oss-20b-Q4_K_M (12 GB)**, dengan `VmRSS 2.264 MB` tetapi `VmSwap 9.455 MB`.
- Model 20B adalah **anak proses** router di port 7070 — bukan unit systemd tersendiri, sehingga mematikan service akan ikut mematikan router.
- `bge-m3` tidak ada; hanya tersedia `nomic-embed-text-v1.5` (768 dim, lemah untuk Bahasa Indonesia).

## 7. Database `rag_roma8`

- Dibuat `CREATE DATABASE rag_roma8 OWNER odoo18` + `CREATE EXTENSION vector, pg_trgm` sebagai `postgres`.
- Hasil: owner `odoo18`, ukuran 7.631 kB, ekstensi `pg_trgm`, `plpgsql`, `vector`.
- Uji hak akses: `CREATE EXTENSION IF NOT EXISTS vector` sebagai `odoo18` (bukan superuser) **berhasil**, dengan `NOTICE: extension "vector" already exists, skipping`.
- Keputusan: SQL hook modul Odoo **tidak perlu** mengubah `vector.control` menjadi `trusted` — cukup ekstensi dibuat superuser lebih dulu. Untuk DB baru, langkah ini wajib diulang.

## 8. Pelepasan model 20B

- Melepas lewat `POST /models/unload {"model":"gpt-oss-20b-Q4_K_M"}` → `{"success":true}`, tanpa mematikan router.
- Swap terpakai turun **10.696 MB → 1.418 MB**.
- RAM `available` naik **6.913 MB → 9.188 MB**; proses 20B berhenti.

## 9. Unduhan model pengganti

- Skrip `nohup` di server dengan `curl -C -` (resume) dan verifikasi ukuran.
- `bge-m3-Q8_0` dari `gpustack/bge-m3-GGUF` — 605 MB.
- `Qwen2.5-7B-Instruct-Q4_K_M` dari `bartowski/Qwen2.5-7B-Instruct-GGUF` — 4.466 MB.
- `Qwen3-4B-Q4_K_M` dari `Qwen/Qwen3-4B-GGUF` — 2.382 MB.
- Throughput stabil ±35 MB/s; semua berkas tunggal (tidak terpecah), bisa langsung dipakai.
- Sebelum dipakai, `--help` build 12032 diperiksa untuk memastikan `--pooling`, `--cache-type-k/v`, `--flash-attn`, `--no-webui` memang ada.

## 10. Layanan embedding

- Unit `llama-embed.service`: `bge-m3` Q8_0, `127.0.0.1:8080`, `--pooling cls`, threads 6.
- Hasil uji `/v1/embeddings`: dimensi **1024**, norma L2 **1.0** (sudah ternormalisasi).
- Latensi 0,07 s per teks (warm), 0,46 s (cold); batch 5 teks 0,24 s.
- RSS sempat 771 MB lalu turun ke 16 MB — normal, bobot di-*mmap* dan halamannya berpindah ke page cache.

## 11. Benchmark model chat

- Alat: [scripts/bench_llama.py](scripts/bench_llama.py) — prompt bergaya RAG Roma 8 (968 token), output 256 token, `temperature 0.2`.
- **Qwen2.5-7B**: prompt eval 37,4 tok/s · generasi **8,3 tok/s** · wall 30,7 s (256 token) · RSS 7.689 MB.
- **Qwen3-4B**: prompt eval 53,7 tok/s · generasi **12,3 tok/s** · wall 21,1 s · RSS 4.765 MB.
- **Prompt caching terbukti aktif**: permintaan kedua dengan prompt identik hanya memproses **1 token** (bukan 968) — hemat ±25 detik per kueri lanjutan.
- Benchmark dijalankan sebagai *background job* karena panggilan pertama melewati batas waktu alat.

## 12. Keputusan model

- **Qwen2.5-7B dijadikan default** meski 48% lebih lambat: kualitas eksposisi Bahasa Indonesia dan kepatuhan *grounding* lebih menentukan.
- Jawaban 300 token selesai ±36 detik — masih di dalam batas HTTP timeout 120–180 detik.
- **Qwen3-4B disimpan sebagai cadangan** (`llama-chat-4b.service`, port 8092, `disabled`).
- Kedua layanan RAG hanya listen di **loopback**, berbeda dari router lama yang terbuka di `0.0.0.0` dengan API key di argv.

## 13. Uji beban memori gabungan

- Odoo + PostgreSQL + Zabbix + embed + chat berjalan bersamaan.
- RAM terpakai **49,5%** dari 15.498 MB; `available` 7.830 MB.
- Penghuni swap tersisa **bukan** dari tumpukan RAG: `docling-serve` 840 MB, `python` 786 MB, `python3` 560 MB, `mysqld` 188 MB.
- `llama-chat` hanya 35 MB swap, `llama-embed` 134 MB.
- Target < 85% tercapai dengan margin lebar; Fase 2 selesai.

## 14. Uji kualitas dan kegagalan varian tekstual

- Pertanyaan uji: *"Apa perbedaan tekstual Roma 8:1 antara Robinson-Pierpont/KJV dan LAI?"*
- Model benar menyebut `κατάκριμα` (katakrima) = penghukuman.
- Namun model menyimpulkan "perbedaan" terletak pada penerjemahan kata itu — padahal RP/KJV dan LAI sama-sama memakai "penghukuman/condemnation".
- Varian yang sesungguhnya justru terlewat: klausa `μὴ κατὰ σάρκα περιπατοῦσιν ἀλλὰ κατὰ πνεῦμα` **ada** di RP/KJV dan **tidak ada** di LAI.
- Diagnosis: bukan semata kelemahan model — konteks diberikan sebagai tiga teks berdampingan tanpa penanda bahwa satu klausa absen, lalu model mengisi kekosongan dengan hipotesis yang salah.
- Pelajaran: *strict grounding* tidak otomatis mencegah halusinasi perbandingan; tanpa metadata, LLM akan "menemukan" pola yang tidak ada.
- Mitigasi dicatat di [PLAN.md §7](PLAN.md): penanda eksplisit `[klausa tidak ada di LAI]`, instruksi membandingkan **kehadiran klausa**, dan routing varian ke jalur `direct lookup`.

## 15. Dokumentasi

- Dibuat `docs/EVALUASI-postgresql.md` — audit lengkap dan instalasi pgvector.
- Dibuat `docs/BENCHMARK-LLAMA.md` — benchmark, konfigurasi layanan, keputusan model.
- Dibuat `STATUS.md` — papan centang terhadap delapan fase.
- Berkas laporan pertama salah ketik (`EVAULASI-postgresql.md`), di-*rename* setelah memverifikasi path absolutnya.
- PLAN asli dan TASK asli diarsipkan apa adanya ke `docs/PLAN-asli.md` dan `docs/TASK-asli.md`.
- `PLAN.md` ditulis ulang sebagai **Revisi 1**, setiap penyimpangan dari rencana awal ditandai **(R1)**.
- Alasan arsip: rencana awal ditulis tanpa data lapangan; menimpanya tanpa jejak akan menghilangkan dasar keputusan.
- Dibuat `PROGRESS.md` (berkas ini) sebagai jurnal.
- Pemeriksaan otomatis tautan relatif menemukan 3 tautan rusak di `BENCHMARK-LLAMA.md` (path `deploy/` dan `scripts/` tidak memakai `../`) — sudah diperbaiki.

## 16. Penelusuran sumber teks Roma 8

- Ditelusuri dan diverifikasi sumber untuk tiga teks: Robinson-Pierpont, KJV, dan LAI.
- **Robinson-Pierpont** — repositori resmi `byztxt/byzantine-majority-text`, **public domain**, edisi RP2018. Tersedia empat bentuk: BETA berparsing, CCAT berdiakritik + apparatus, CSV Unicode, dan TEI-XML.
- Ditemukan tiga berkas CSV yang semuanya terpakai: `ccat/no-variants` (berdiakritik), `ccat/with-variants` (berdiakritik + apparatus), `strongs/with-parsing` (tanpa aksen + parsing + Strong's).
- Diverifikasi dengan unduhan nyata: `ROM.csv` terbaca, Roma 8:1 tampil benar di ketiga bentuk.
- **KJV** — `ebible.org/Scriptures/eng-kjv_vpl.zip`, **public domain** di luar Inggris. Format *verse-per-line* paling mudah diparsing.
- Ditemukan bahwa KJV menandai kata sisipan penerjemah dengan `[...]` — harus dibuang saat normalisasi.
- **LAI** — berhak cipta. Kebijakan resmi mengizinkan non-komersial hingga 1.000 ayat **dan** bukan satu kitab utuh, dengan atribusi wajib `Dikutip dari ALKITAB (TB) © LAI 1974`. Roma 8 = 39 ayat, jadi memenuhi.
- Ditemukan **Bible API resmi LAI** (`bible-api.alkitab.or.id`). Diuji tanpa token → **HTTP 400**, jadi memang wajib kunci API.
- Alternatif yang diuji dan dinilai: SABDA API mengembalikan **HTML** (bukan JSON) sehingga rapuh; situs `alkitab.or.id` merender teks via JavaScript sehingga tidak bisa di-`curl`; AYT berlisensi CC BY-ND.
- **Temuan paling berdampak:** berkas `with-variants` menyimpan apparatus inline — `μὴ {NA μὴ κατὰ σάρκα περιπατοῦσιν ἀλλὰ κατὰ πνεῦμα > - } …`. Notasi `> -` menandai bahwa NA/teks eklektik **menghilangkan** klausa 8:1b.
- Konsekuensi: varian tekstual **tidak perlu disimpulkan LLM**, cukup diurai dari apparatus menjadi data. Ini menutup kegagalan yang tercatat di bagian 14.
- Konsekuensi kedua: kolom *stripped Greek* sebaiknya diisi langsung dari berkas `with-parsing` saat impor, bukan hasil normalisasi runtime.
- Berkas uji disimpan di `/home/nms/rag-roma8/src/` (5 berkas). Rincian: [docs/SUMBER-TEKS.md](docs/SUMBER-TEKS.md).

## 17. Keputusan tentang leksikon

- Muncul pertanyaan apakah perlu mengunduh Thayer's Lexicon.
- Dianalisis: Strong's + parsing code sudah memberi gloss singkat dan kategori gramatikal, cukup untuk pertanyaan jenis "kata Yunani apa" dan "apa kategorinya".
- Disadari yang sebenarnya lebih mendesak **bukan leksikon**, melainkan **decoder parsing code** (`{V-PAP-DPM}` → "verba, present, aktif, partisip, datif, plural, maskulin") — tanpa itu model tidak bisa membaca apa pun.
- Thayer's dinilai: public domain, kecil, tetapi **usang** (1889) dan justru lemah pada kata jarang seperti `κατάκριμα`.
- Dibandingkan: Abbott-Smith (1922, public domain) lebih baik untuk PB; STEPBible TBESG lisensinya kontradiktif antar halaman; BDAG berhak cipta dan tidak bisa didistribusikan.
- **Keputusan:** leksikon **ditunda**, dibuat sebagai tabel terpisah yang dipanggil via nomor Strong's saat membangun konteks — **tidak** di-embed, agar penambahannya tidak mengubah skema dan tidak memaksa re-embed.

## 18. Desain skema (collection & field)

- Dirancang skema lengkap: **15 tabel** dan **1 collection pencarian** (`rag_chunk`). *(Kemudian bertambah 2 tabel ekspansi kueri — lihat §29 dan [DESAIN-SKEMA.md](docs/DESAIN-SKEMA.md) §12b; jumlah akhir 17 tabel inti.)*
- Ditegaskan pemetaan konsep: "collection" di tumpukan ini = 1 tabel + kolom `vector` + indeks HNSW, karena PostgreSQL adalah vector database-nya.
- Diputuskan hanya **satu** collection, karena perikop/varian/leksikon adalah konteks yang di-join, bukan target pencarian vektor.
- Empat tabel master enumerasi dibuat (`rag_chunk_kind`, `rag_witness`, `rag_variant_type`, `rag_query_route`) agar aturan "referensi lewat `Many2one`, `Selection` hanya untuk `state`" benar-benar dipatuhi.
- Diputuskan teks **didenormalisasi** ke `rag_chunk`, karena kolom `GENERATED tsvector` tidak bisa merujuk tabel lain; `rag_verse` tetap sumber kebenaran.
- Dipisahkan `rag_query_hit` dari `rag_query_log`, agar evaluasi Fase 8 bisa mengukur peringkat ayat yang benar-benar terambil.
- Ditambahkan `rag_embedding_model` agar pergantian model tidak mencampur vektor berdimensi berbeda tanpa jejak.
- Dirancang komposisi `embed_text`: Yunani berdiakritik **tidak** di-embed; dipakai transliterasi + lema + gloss Strong's agar pertanyaan Indonesia dapat bertemu kata Yunani.
- Diuji langsung di PostgreSQL 16: `tsvector GENERATED ALWAYS` berhasil, GIN berfungsi, **kata Yunani ikut terindeks** (`κατακριμα` ditemukan), HNSW `(m=16, ef_construction=64)` berhasil, dan query RRF penuh mengembalikan peringkat gabungan yang benar.
- Diukur: kolom `vector(1024)` = **4.100 byte/baris**, sehingga 39 ayat hanya ≈160 KB — tuning HNSW tidak relevan untuk skala ini.
- Ditemukan bahwa konfigurasi teks `'simple'` **sudah memadai** untuk Yunani tanpa aksen, sehingga konfigurasi bahasa khusus tidak diperlukan.
- Satu kesalahan kecil saat uji: `pg_size_pretty(pg_column_size(...))` ambigu antara `integer` dan `bigint`; diperbaiki dengan cast eksplisit.
- Dokumen: [docs/DESAIN-SKEMA.md](docs/DESAIN-SKEMA.md).

## 19. Sinkronisasi dokumen

- `PLAN.md` dinaikkan ke **Revisi 2**: menambahkan kepastian sumber teks dan skema data, tanpa mengubah arah.
- `TASK.md` dibuat di akar sebagai daftar tugas revisi, dengan butir `[x]` hanya untuk yang **sudah diverifikasi**.
- Ditambahkan Fase 0 (fondasi & audit) yang tidak ada di daftar awal.
- Ditambahkan butir yang muncul dari temuan: decoder parsing, parser apparatus, backoff cron, uji regresi varian 8:1.
- Pemeriksaan otomatis tautan relatif menemukan 3 tautan rusak di `DESAIN-SKEMA.md` (berkas berada di `docs/`) — sudah diperbaiki.

## 20. Eksekusi Fase 1 — akuisisi & kurasi 39 ayat

- Diputuskan memakai **AYT** untuk Bahasa Indonesia karena dapat diunduh langsung tanpa API, sementara LAI baru bisa lewat kunci.
- Diunduh lima berkas mentah: 3 CSV Robinson-Pierpont, `eng-kjv_vpl.zip`, dan `indayt_vpl.zip`, seluruhnya ke `data/raw/`.
- Ditemukan kesalahan sendiri: dua unduhan RP ditulis ke nama berkas yang sama, sehingga versi berdiakritik tertimpa versi apparatus. Diperbaiki dengan nama eksplisit (`ROM_accented.csv`, `ROM_variants.csv`).
- Ditulis `scripts/fase1_build.py` yang menggabungkan empat sumber menjadi satu dataset selaras per ayat.
- **Verifikasi lulus**: 39 ayat hadir di keempat sumber, tidak ada nomor hilang, dan jumlah kata Yunani berdiakritik sama dengan jumlah kata pada berkas Strong's **di setiap ayat**.
- Total **663 kata** Yunani, semuanya memiliki nomor Strong's dan kode parsing.
- Apparatus diurai menjadi **21 varian**: 18 substitusi dan 3 omit (8:1, 8:11, 8:26).
- Ditemukan dan diperbaiki dua cacat data:
  - `¶` (penanda paragraf RP) terbawa ke teks Yunani pada 8:12, 18, 26, 31 — dipisahkan menjadi field `paragraph_start`, bukan dibuang.
  - 8:28 memuat `παντα 3956 {A-APN} 3956 {A-NPN}` — satu kata dengan **dua parsing alternatif**; parser awal gagal dan menyisakan token. Diperbaiki: parser kini menerima banyak pasangan nomor+kode untuk satu kata, dan **melempar galat** bila ada token tak terurai (agar kegagalan tidak lagi senyap).
- Dibuat transliterasi Yunani→Latin untuk kebutuhan `embed_text`, karena Yunani berdiakritik tidak layak di-embed langsung.
- Disusun 4 perikop dan dikonfirmasi silang dengan penanda `¶` RP — tiga dari empat penanda jatuh tepat di batas perikop, satu (8:26) merupakan pemisah paragraf internal.
- Disusun `istilah-kunci.csv`: 27 istilah teologis dengan nomor Strong's, lemma, gloss, dan daftar ayat kemunculan. Yang terbanyak: `πνεῦμα` dan `θεός` (15 ayat), `σάρξ` (10), `Χριστός` (9).
- Dicatat perbedaan lisensi AYT: berkas `about` menyebut **BY-NC-SA**, halaman eBible menyebut **BY-ND 4.0**. Keduanya mengizinkan penggunaan non-komersial dengan atribusi; perbedaannya pada izin turunan. Atribusi `AYT © 2011–2024 YLSA-AYT` disimpan di dataset.
- Ditegaskan AYT **bukan** TB: 8:1 AYT "Karena itu, sekarang tidak ada lagi penghukuman…" vs TB "Demikianlah sekarang tidak ada penghukuman…". Bila kunci LAI diperoleh, kolom `ind` bisa diganti tanpa mengubah struktur.
- Keluaran: `roma8.json` (150 KB), `roma8.csv`, `roma8_variants.csv`, `istilah-kunci.csv`, `VERIFIKASI.md`, dan `data/README.md`.

## 21. Fase 4 — modul Odoo `rag_teologi`

- Modul dibangun langsung di server: `/opt/odoo18/addons/rag_teologi`, owner `odoo18:odoo18`.
- Sumber tetap disimpan di repo (`module/rag_teologi/`) agar bisa di-*version control*; server menerima salinan lewat SFTP.
- Ditambahkan mode `--put` pada `scripts/rrun.py` untuk unggah berkas (SFTP), karena menulis ke `/opt/odoo18` butuh sudo dan menyalin isi berkas lewat `exec_command` tidak praktis.
- Ditulis 15 model, 4 tabel master enumerasi, 19 view, 10 aksi, 14 menu, 2 grup, 29 baris ACL, 4 record rule, dan data awal (jenis unit, saksi, jenis varian, jalur kueri, model embedding, templat prompt, konfigurasi).
- **Kegagalan pertama:** modul ditolak dengan *"has an incompatible version, setting installable=False"*. Penyebabnya server menjalankan **Odoo 18.2alpha1**, bukan 18.0 seperti yang dilaporkan `odoo --version` di laptop. Manifest diperbaiki menjadi `18.2.1.0.0`.
- **Kegagalan kedua:** `_sql_constraints` sudah **dihapus** di 18.2 — hanya memunculkan peringatan dan diabaikan, sehingga seluruh constraint tidak akan pernah dibuat. Diganti menjadi atribut `models.Constraint(sql, pesan)`; 10 blok dikonversi.
- **Kegagalan ketiga:** `_auto_init()` pada `rag.chunk` berjalan sebelum tabel `rag_config` dibuat, sehingga indeks `rag_config_active_uniq` gagal (`relation "rag_config" does not exist`) dan registry gagal dimuat. Hook dibuat memeriksa keberadaan tabel, dan `post_init_hook` memanggilnya sekali lagi setelah semua tabel siap.
- **Kegagalan keempat:** field `display_name` yang saya deklarasikan bertabrakan dengan field khusus Odoo; nilainya selalu `False`. Diganti menjadi field `label` dengan `_rec_name = 'label'`.
- **Kegagalan kelima:** `write()` pada ayat tidak menurunkan status ke `chunked` dan tidak menandai chunk terkait kotor, sehingga perubahan teks tidak akan pernah memicu re-embedding. Diperbaiki: perubahan teks menurunkan status ayat `embedded → chunked` dan menandai semua chunk-nya `dirty`.
- Kesalahan pada skrip uji sendiri juga tercatat: `name_get()` sudah dihapus di Odoo 18, dan `/tmp` lokal ternyata privat per perintah sehingga berkas uji hilang — berkas uji kemudian disimpan di `module/tests/`.
- Ditemukan duplikasi indeks `dirty` (btree dari `index=True` + indeks parsial buatan hook); `index=True` dihapus.
- Dibuat `scripts/deploy_module.sh` yang memeriksa sintaks Python & XML, mengemas, mengunggah, memasang, menjalankan `-i`/`-u`, lalu me-restart layanan.
- **Hasil uji fungsional** (semua data di-*rollback*): label chunk benar, vektor + 4 kolom non-ORM terisi, FTS Yunani (`κατακριμα`) dan Indonesia (`penghukuman`) menemukan baris yang sama, cosine ke diri sendiri `1.0`, varian NA/omission tersimpan, query log + hit tercatat, `word_count` terhitung, dua constraint database menolak duplikat dengan benar, dan `-u` berjalan **0 galat**.
- Layanan `odoo18.service` di-restart; status `active`, HTTP 8069 merespons 303 (redirect login, normal). Modul tercatat `installed` versi `18.2.1.0.0` dengan 14 menu.
- Dokumentasi: [docs/MODUL-ODOO.md](docs/MODUL-ODOO.md).

## 22. Fase 5 (sebagian) — impor ayat, perikop, varian

- Diminta menjalankan impor saja: **tanpa** chunking dan tanpa embedding.
- Dibuat wizard `rag.import.wizard` (TransientModel) di modul `rag_teologi`: menerima berkas JSON yang diunggah atau path di server, memperbarui data yang sudah ada (upsert), dan mencatat hasilnya ke `rag.import.batch`.
- Ditambahkan menu *Konfigurasi → Impor Dataset…* dan view wizard, sehingga impor bisa dijalankan dari UI tanpa shell.
- Parser apparatus memetakan `witness` dan `type` dari dataset ke master `rag_witness` dan `rag_variant_type`; bila master tidak ada, impor melempar galat yang jelas alih-alih membuat data setengah jadi.
- **Kegagalan pertama:** 18 ayat masuk, 21 gagal, 0 varian. Penelusuran awalnya buntu karena `ir_logging` kosong dan log hanya memuat SQL mentah.
- Diperbaiki dengan menambahkan pencatatan galat per baris ke `log` batch — praktik yang seharusnya ada sejak awal.
- **Akar masalah ditemukan dari log baru:** `Verse.create(...)` tidak di-*assign* ke variabel `verse`, sehingga `verse.id` kosong. Akibatnya `rag_variant.verse_id` bernilai NULL, savepoint baris bergulir, dan perikop yang baru dibuat ikut batal sementara cache `perikop_cache` masih memegang id-nya. Semua ayat berikutnya di perikop itu lalu gagal `rag_verse_pericope_id_fkey`.
- Perbaikan: hasil `create` di-*assign*; hitungan `perikop`/`ayat_baru`/`varian` dipindah ke blok `else` agar tidak menghitung baris yang batal; dan `perikop_cache` dibersihkan serta `env.invalidate_all()` dipanggil saat baris gagal.
- Data parsial dibersihkan lebih dulu sebelum impor ulang, supaya keadaan akhir persis sama dengan dataset (bukan campuran hasil dua percobaan).
- **Hasil akhir:** 1 kitab, **4 perikop**, **39 ayat**, **21 varian**, 0 gagal. Tidak ada chunk (0 baris) dan tidak ada vektor — sesuai permintaan.
- Diverifikasi: seluruh 39 ayat berstatus `draft` dengan `dirty=true`; tidak ada ayat tanpa perikop; pembagian perikop tepat (11 + 6 + 13 + 9); 14 ayat memiliki varian (18 substitusi, 3 omit); Roma 8:1 memuat `NA/omission` dengan bacaan Byzantine yang dihilangkan NA.
- **Uji idempotensi:** impor kedua menghasilkan jumlah identik (1/4/39/21/0) — tidak ada duplikasi.

## 23. Fase 5 penuh — decoder morfologi, chunking, embed_text

- Diminta menyelesaikan Fase 5 secara penuh: chunking dan komposisi `embed_text`, tetap tanpa memanggil layanan embedding.
- Ditambahkan **decoder morfologi** `models/morph.py`, ditulis sebagai modul Python murni (tanpa impor Odoo) supaya bisa diuji berdiri sendiri.
- Spesifikasi kode diambil dari `source/README.md` repositori Robinson-Pierpont, bukan dari terkaan — penting karena kode seperti `V-PNI-3S` dan `A-NSN-N` mudah salah dibaca.
- Tiga kesalahan decoder ditemukan lewat pengujian dan diperbaiki:
  - `V-2AAI-3S` (aorist kedua) awalnya gagal karena awalan `2A` ikut menelan huruf tense.
  - `PRT-N` salah dibaca sebagai "partikel, nominatif" — sufiks `-N` pada partikel berarti negatif, bukan kasus. Perbaikannya: pola kasus–jumlah–gender hanya berlaku untuk kelompok nominal.
  - `N-PRI` (nama diri) menghasilkan "plural, ri"; ditambahkan tabel kode khusus (`PRI`, `LI`, `T`).
- Hasil: **146 dari 146 kode** yang muncul di Roma 8 terurai, diverifikasi dengan kriteria yang menolak sisa kode mentah di dalam teks hasil.
- Ditambahkan **Strong's Greek Dictionary** (Open Scriptures, public domain) untuk glos per kata: `scripts/build_strongs_gloss.py` mengubah `strongsgreek.dat` menjadi `data/strongs_greek.json` (5.624 entri).
- Glos mentah bergaya konkordansi ("ghost, life, spirit(-ual, -ually), mind") dirapikan: kurung dibuang, "Compare NNNN" dibuang, maksimum empat pengertian.
- Dibangun **chunking engine** `models/chunker.py` dengan komposisi `embed_text` enam baris: ID, EN, YUNANI, TRANS, LEMA, GLOSS. Yunani berdiakritik sengaja tidak dipakai; dipakai bentuk tanpa aksen + transliterasi.
- Ditambahkan `lexeme_text` = transliterasi lema Strong's + token morfologi hasil decoder (mis. `aorist`, `partisip`, `datif`), sehingga pertanyaan gramatikal bisa ditemukan lewat full-text.
- **Kegagalan (kualitas):** percobaan pertama menghasilkan baris GLOSS sepanjang ±1.000 karakter berisi sampah konkordansi (`any, aught, man, neither any`). Diperbaiki: dua pengertian pertama per kata, maksimum 25 entri, dipotong 700 karakter. Panjang `embed_text` 8:1 turun dari 866 ke 693 karakter.
- Dibuat wizard **`rag.chunking.wizard`** dan menu *Konfigurasi → Jalankan Chunking*, sehingga proses bisa diulang dari UI.
- **Hasil:** 39 chunk untuk 39 ayat, 0 gagal; seluruh ayat beralih `draft → chunked`; `embed_text` dan `embed_hash` terisi; `embedding` tetap kosong sesuai instruksi.
- Verifikasi: `token_est` 95–297 (rata-rata 186); kolom FTS terisi 39/39; pencarian "katakrima" (lema) menemukan 1 chunk, "aorist" (morfologi) 17 chunk, "penghukuman" (Indonesia) 1 chunk, "κατακριμα" (Yunani) 1 chunk.
- Uji idempotensi: chunking ulang tetap 39 chunk, tidak ada duplikasi, dan hash berubah hanya ketika aturan komposisi berubah.
- Uji dirty flag pada chunk nyata: mengubah teks ayat menandai chunk kotor; chunking ulang mengubah `embed_hash`. Diuji dalam transaksi yang di-*rollback*.

## 24. Fase 6 — embedding otomatis

- Ditulis klien HTTP `models/embedding_client.py`: `POST /v1/embeddings`, timeout dari konfigurasi, 3× percobaan dengan backoff eksponensial. Galat 4xx **tidak** diulang karena mengulang permintaan yang salah tidak akan menolong; hanya galat jaringan/5xx yang diulang.
- Ditambahkan field `api_model` pada `rag.embedding.model` karena nilai `model` yang dikirim ke API harus sama dengan `--alias` llama-server (`bge-m3`), bukan nama internal (`bge-m3-Q8_0`).
- Ditulis antrean `_cron_embed` (batch 16) + aksi server + `ir.cron` **RAG: Embedding Chunk** tiap 5 menit.
- Ditambahkan tombol manual *Re-embed* pada list/form chunk dan *Re-embed Chunk* pada form ayat, khusus RAG Manager.
- **Kegagalan penting (dan pelajaran):** tombol manual tampak berhasil (`embedded_at` berubah) tetapi status akhirnya kembali `chunked`. Penelusuran menunjukkan **Odoo 18 menunda `write()` ORM sampai flush** — `write(state='chunked')` baru dieksekusi ke SQL *setelah* `_embed` menulis vektor lewat SQL mentah, lalu menimpa hasilnya. Perbaikan: `self.env.flush_all()` sebelum menulis vektor.
- Perbaikan itu tidak akan ditemukan tanpa menguji tombol; `_cron_embed` kebetulan tidak terpengaruh karena tidak ada `write()` tertunda sebelumnya.
- **Hasil:** 39 chunk ter-embed dalam **29 detik**, seluruhnya 1024 dimensi, tidak ada yang gagal. Ayat ikut beralih ke `embedded`, `dirty` menjadi `false`.
- Diverifikasi rencana eksekusi memakai **Index Scan HNSW** (`rag_chunk_embedding_hnsw`), bukan seq scan.
- Uji jalur galat: endpoint diarahkan ke port mati → `retry_count=1`, `last_error` terisi, status tetap `chunked`; setelah endpoint dipulihkan, embedding berhasil dan `retry_count` kembali 0.
- **Uji kualitas pencarian semantik (6 kueri):** 5 tepat sasaran — penghukuman→8:1 (0,659), kemuliaan→8:18 (0,532), Roh menolong→8:26 (0,696), kasih Allah→8:39 (0,585), hidup menurut daging→8:5 (0,678).
- **Satu kueri meleset:** "pengangkatan menjadi anak Allah" mengembalikan 8:14/8:17/8:19, bukan 8:23 (`υἱοθεσία`). Ditelusuri: full-text **menemukan** 8:23 untuk kata "pengangkatan", tetapi `plainto_tsquery` meng-AND semua kata sehingga "pengangkatan menjadi anak Allah" gagal; dengan OR pun 8:23 masih di luar lima besar.
- Kesimpulan untuk Fase 7: RRF saja tidak cukup bila kueri FTS terlalu ketat. Perlu `websearch_to_tsquery` atau penggabungan OR, ditambah pemetaan istilah (υἱοθεσία → pengangkatan/adopsi) sebagai ekspansi kueri.

## 25. Inti Fase 7 — lima transaksi kueri

- Diminta membuat 5 transaksi untuk fungsi Kueri. Karena fungsi itu belum ada, dibangun dulu intinya: Query Router, Hybrid RRF, Context Builder, dan konsol Tanya RAG.
- **Query Router** memakai regex `Roma 8:N` / `8:N-M` → rute `direct`; tanpa nomor ayat → `hybrid`.
- **Hybrid search**: dense (`<=>` cosine) + full-text, digabung RRF k=60. Tsquery dibangun dengan **OR** antar kata dan stopword dibuang — ini perbaikan langsung dari temuan Fase 6 bahwa `plainto_tsquery` meng-AND seluruh kalimat.
- **Context Builder** menyusun blok per perikop: Yunani, KJV, AYT, **baris morfologi**, lalu blok `[VARIAN TEKSTUAL]` terpisah di akhir, plus baris `[SUMBER]` yang menegaskan AYT bukan TB/LAI.
- Ditambahkan konsol `rag.query.wizard` + menu *Kueri → Tanya RAG*.
- **Kegagalan pertama:** dua kueri gagal `NameError: name 'c' is not defined` karena daftar hasil ditulis sebagai list literal, bukan comprehension (lupa `for c in chunks`).
- **Kegagalan kedua (kualitas):** jawaban soal `κατάκριμα` menyebut "akusatif, partikel" — salah. Penyebabnya konteks tidak memuat morfologi sama sekali, padahal decoder sudah ada. Setelah baris `Morf` ditambahkan, jawaban menjadi "nomina, nominatif, tunggal, netral" — benar.
- **Kegagalan ketiga (integritas data):** jawaban kueri 4 menyebut AYT berbunyi "(uji) (uji)". Ternyata uji tombol re-embed sebelumnya menulis teks uji ke ayat 8:1, dan `action_reembed` memanggil `env.cr.commit()` di dalamnya sehingga `rollback` di skrip uji tidak membatalkan apa pun. Teks ayat dipulihkan dari dataset.
- **Bug desain yang ikut terungkap:** `content_hash` tidak berubah ketika teks diedit, sehingga pemeriksaan berbasis hash menyatakan "tidak ada perbedaan" padahal teks sudah rusak. Field diubah menjadi **computed stored** dengan `@api.depends` pada empat kolom teks.
- Dataset juga dipindahkan dari dalam modul ke `/opt/odoo18/rag-data/` karena setiap deploy menghapus isi direktori modul.
- **Hasil: 5 transaksi, semuanya sukses, 17 hit.** *(Per 2026-11-21 total sudah 9 transaksi / 33 hit — lihat STATUS.md.)* Rute: 2 direct + 3 hybrid. Latensi 40–135 detik (rata-rata 84 detik), prompt 713–2.817 token, generasi 97–480 token.
- Kueri 1 (Roma 8:1): menyebut varian NA yang menghilangkan klausa Byzantine — sesuai tujuan.
- Kueri 2 (mengapa tidak ada penghukuman): 8:1 peringkat 1 pada dense maupun FTS, jawaban mengutip Yunani/KJV/AYT.
- Kueri 3 (κατάκριμα): morfologi benar setelah perbaikan konteks.
- Kueri 4 (KJV vs AYT): menjelaskan klausa yang hilang di AYT — perbaikan dari kegagalan smoke test di sesi awal.
- Kueri 5 (alur argumen): 8:18 peringkat 1, tetapi jawaban terpotong pada 480 token.
- Catatan kecil yang dirapikan: rank kosong pada rute direct tersimpan sebagai `0`, bukan NULL; dan frasa varian "…(bacaan Byzantine)" ambigu — diperbaiki menjadi "klausa itu ADA pada bacaan Byzantine".

## 26. Perbaikan tampilan form Kueri

- Dilaporkan lewat tangkapan layar: kolom Pertanyaan dan Jawaban hanya selebar ±200 px sehingga teks terpotong satu-dua kata per baris.
- Penyebabnya bukan lebar layar, melainkan penempatan: `question` dan `answer` berada di dalam `<group>`, dan `<group>` membagi area menjadi dua kolom. Odoo hanya memberi lebar penuh pada field yang menjadi **anak langsung `<sheet>`**.
- Perbaikan: kedua field dipindah ke luar `<group>`, diberi `nolabel="1"` dan `class="w-100"`, dengan `<separator>` sebagai judul. Pola yang sama diterapkan pada konsol *Tanya RAG*.
- Ditemukan juga: `latency_ms` tampil `120,818` karena pemisah ribuan. Ditambahkan field terhitung `latency_s` ("120,8 s") dan dipakai di form serta list, sehingga tidak lagi terbaca seperti angka desimal.
- Arsitektur view diverifikasi langsung dari `ir_ui_view` di database untuk memastikan field benar-benar sudah di luar `<group>`.

## 27. Tombol eksekusi pada Riwayat Kueri

- Dilaporkan: pengguna membuat record kueri baru di *Riwayat Kueri* lalu bingung cara menjalankannya.
- Akar masalahnya konseptual: `rag.query.log` adalah tabel **audit**, bukan tempat mengajukan kueri. Membuat record hanya menyimpan pertanyaan tanpa mengeksekusi apa pun — dulu pun statusnya langsung `success` meski belum berjalan.
- Ditambahkan state `draft` dan `running` (default `draft`), tombol **Jalankan Kueri** pada header form dan ikon ▶ pada list, keduanya hanya tampil saat `draft`/`error`.
- Layanan kueri dipecah: `ask()` membuat record lalu memanggil `_jalankan(log)`; `_jalankan` menerima record yang sudah ada sehingga bisa dipakai tombol.
- Eksekusi ulang membersihkan hit lama lebih dulu, sehingga menjalankan tombol dua kali tidak menggandakan `rag.query_hit`.
- Tombol mengembalikan aksi yang **memuat ulang form**, bukan sekadar notifikasi, agar jawaban langsung terlihat.
- Record kueri lama yang belum pernah berjalan (latensi kosong) diubah menjadi `draft` supaya tombolnya muncul.
- **Temuan saat deploy:** upgrade sempat memicu `CRITICAL … Failed to initialize database` karena `ALTER TABLE rag_chunk ADD COLUMN IF NOT EXISTS` **tetap mengambil lock eksklusif** dan bertabrakan dengan layanan yang sedang melayani permintaan (lock timeout). Hook dibuat benar-benar idempoten: kolom dan indeks diperiksa lewat `information_schema`/`pg_class` lebih dulu, dan DDL hanya dijalankan bila memang belum ada. Upgrade berikutnya 0 galat.
- Log deploy juga ternyata **ditambahkan**, bukan ditimpa, sehingga galat lama terbaca seolah baru. Skrip deploy sekarang mengosongkan log lebih dulu.
- **Temuan kedua:** ketiga wizard (impor, chunking, kueri) tidak punya baris ACL, sehingga hanya admin yang bisa membukanya. Ditambahkan 3 baris ACL; peringatan Odoo hilang.
- Diuji dengan pengguna ber-grup RAG User saja: ubah konfigurasi/ayat/varian, buka chunking, dan buka impor semuanya **ditolak**; baca ayat/chunk, buka konsol, dan buat kueri **diizinkan**.
- Kesalahan pada skrip uji sendiri: `write()` pada recordset kosong tidak memicu pemeriksaan akses, sehingga sempat tampak seolah RAG User bisa mengubah konfigurasi. Setelah diuji dengan record nyata, hasilnya benar.

## 28. Mengapa 8:29–30 tidak muncul pada kueri 20

- Pertanyaan: *"Bagaimana pandangan Paulus mengenai keselamatan?"* — kueri id 20 mengambil 8:24, 8:38, 8:6, 8:35, 8:15, tanpa 8:29–30.
- Ditelusuri dengan mengukur peringkat, bukan menduga. Empat sebab bertumpuk:
  - **FTS nol hasil.** Tsquery menjadi `pandangan | Paulus | mengenai | keselamatan`; keempat kata itu tidak ada di Roma 8. RRF jadi ekuivalen dengan dense saja.
  - **`top_k_dense=20`**: 8:30 berada di peringkat **35**, tidak pernah menjadi kandidat.
  - **`top_k_final=5`**: 8:29 berada di peringkat **20**, jadi kandidat tetapi tidak masuk konteks.
  - **Tidak ada perluasan perikop**: konteks hanya berisi ayat yang terambil, padahal PLAN §5 menetapkan parent = perikop.
- Diperbaiki: Context Builder kini menyertakan **perikop dari hit peringkat 1 secara utuh** (ayat terambil ditandai ▶, sisanya ringkas satu baris), sedangkan perikop lain hanya ayat terambil + tetangga ±1. Blok varian dihitung lebih dulu agar tidak termakan pemotongan anggaran.
- Percobaan pertama terlalu boros: lima hit menyentuh empat perikop sehingga konteks tepat 6000 karakter dan terpotong. Aturan di atas menurunkannya ke 5.836 karakter tanpa kehilangan 8:29–30.
- Diverifikasi: konteks memuat 8:29 dan 8:30 lengkap dengan teks AYT, dan blok `[VARIAN TEKSTUAL]` tetap utuh di akhir.
- **Namun jawaban tetap tidak menyebut 8:29–30.** Model hanya membahas ayat bertanda ▶. Ditambahkan templat prompt **v2** yang memerintahkan menelusuri seluruh perikop, bukan hanya ayat bertanda. Hasilnya membaik — model kini menelusuri 8:18, 23, 24, 26–27, 35, 37 — tetapi tetap melewati 29–30. Ini batas kemampuan model 7B dengan konteks ±2.800 token, bukan kegagalan retrieval.
- Diukur frasa mana yang benar-benar menarik 8:29–30:
  - "predestinasi dan rencana Allah" → 8:29 **peringkat 1**, 8:30 **peringkat 2**
  - "Allah menetapkan sejak semula…" → 1 dan 7
  - "rantai emas keselamatan…" → 24 dan 2
  - "Jelaskan Roma 8:28-30" → rute **direct**, jadi nomor ayat dijamin diambil
  - "pandangan Paulus mengenai keselamatan" → 20 dan 35
- Kesimpulan: pertanyaan generik memang menyebar ke seluruh pasal. Untuk "golden chain", pakai kosakata yang tepat (predestinasi/rencana Allah) atau sebut nomor ayatnya.

## 29. Ekspansi kueri (sinonim teologis)

- Diminta mengerjakan opsi pertama: ekspansi kueri. Dibuat dua model baru: `rag.query.expansion` (istilah) dan `rag.query.expansion.line` (padanan), dengan 12 istilah awal — keselamatan, penghukuman, kemuliaan, anak, roh, daging, pengharapan, iman, kasih, hukum, maut, predestinasi.
- `_tsquery` kini mengembalikan **(tsquery, daftar padanan)**; padanan ditambahkan ke kueri full-text dan dicatat di `stage_ms['expanded']` agar keputusan pencarian bisa diaudit.
- Contoh: "keselamatan" → `keselamatan | diselamatkan | penebusan | dibenarkan | dimuliakan | dipanggil | ditetapkan | serupa`.
- **Dampak terukur:** full-text yang sebelumnya **nol** hasil kini menemukan 5 chunk. Roma 8:29 naik dari peringkat dense 20 menjadi **peringkat 3 RRF**; 8:28 masuk peringkat 2.
- 8:30 tetap tidak menjadi hit (dense 35, FTS di bawah 5), tetapi masuk konteks lewat perluasan perikop dari hit peringkat 1.
- **Kegagalan saat uji pertama:** `stage['expanded']` berisi daftar, lalu `sum(stage.values())` melempar `TypeError: int + list`. Diperbaiki dengan menjumlahkan hanya nilai numerik. Log berstatus `error` dari percobaan itu dibersihkan.
- **Hasil akhir:** kueri "Bagaimana pandangan Paulus mengenai keselamatan?" kini menjawab dengan menyebut **Roma 8:29–30** ("mereka yang dipanggil… dibenarkan… dimuliakan"), sesuatu yang tidak terjadi pada kueri 20 semula.
- Ditambahkan menu *Konfigurasi → Ekspansi Kueri* agar RAG Manager bisa menambah padanan tanpa mengubah kode, plus 4 baris ACL (user baca, manager kelola).

## 30. Tab teks asli pada jawaban

- Diminta menampilkan bahasa asli ayat yang dikutip sebagai notebook pada jawaban.
- Form riwayat kueri kini memakai notebook: tab **Jawaban**, **Teks Asli (Yunani)**, Ayat Terambil, Parameter, Galat. Konsol *Tanya RAG* juga mendapat dua tab pertama.
- Field `greek_quotes` dihitung dari **ayat yang benar-benar dikutip di jawaban**, bukan hanya dari hasil pencarian. Urutannya: ayat dikutip → cari `rag.verse` → tampilkan Yunani berdiakritik, transliterasi, dan bentuk tanpa aksen.
- Setiap ayat diberi keterangan asal: **hasil pencarian** atau **konteks perikop**. Ini penting karena 8:30 dikutip jawaban tetapi bukan hasil pencarian — ia masuk lewat perluasan perikop.
- Contoh keluaran untuk kueri 27: 8:18 (konteks), 8:24 (hasil), 8:26 (konteks), 8:29 (hasil), 8:30 (konteks) — persis ayat yang disebut jawaban.
- Bila jawaban belum menyebut ayat, tab menampilkan ayat yang terambil dengan keterangan eksplisit, bukan halaman kosong.
- **Kesalahan yang saya buat dan perbaiki:** saat menyisipkan metode baru, saya memakai `str.index()` untuk memotong berkas, tetapi penanda akhirnya muncul lebih awal dari penanda awal — akibatnya seluruh blok dari `_compute_name` sampai akhir tergandakan dan `_compute_greek_quotes` terdefinisi dua kali (yang lama menang). Berkas model ditulis ulang utuh, bukan ditambal, lalu diverifikasi hanya ada satu definisi.

## 31. Pilihan Pengaturan RAG per kueri

- Diminta agar konsol *Tanya RAG* punya pilihan dari "Pengaturan RAG", supaya satu kueri bisa memakai preset tertentu.
- Ternyata field `config_id` sudah ada tetapi dibatasi `groups="group_rag_manager"` — RAG User tidak bisa melihatnya. Batasan dihapus, ditambah `domain active=True` dan `no_create`.
- **Penghalang struktural:** indeks unik parsial `rag_config_active_uniq` hanya mengizinkan **satu** konfigurasi aktif, sehingga praktis tidak ada yang bisa dipilih. Indeks dihapus lewat hook (idempoten), dan `get_active()` diubah memakai `order='sequence, id'` sehingga konfigurasi aktif berurutan terkecil menjadi default.
- Ditambahkan field `sequence` pada `rag.config` untuk mengatur prioritas preset.
- **Pengaman baru:** memilih konfigurasi dengan model embedding berbeda akan membandingkan ruang vektor yang tidak sepadan. Layanan kini memeriksa `rag_chunk.embedding_model_id` dan menolak dengan pesan jelas bila tidak cocok.
- Info pada konsol kini menyebut konfigurasi yang dipakai, bukan hanya jalur dan latensi.
- Diuji: preset kedua dengan `max_tokens=200` dipakai untuk kueri "Roma 8:15" — tercatat di `config_id`, jawaban 138 token (di bawah batas), durasi 42 detik. Konfigurasi dengan model 768 dimensi ditolak dengan pesan yang menyebut kedua model. Default tetap "Roma 8 — lokal".
- Artefak uji (dua preset, satu model embedding palsu, dan log kuerinya) dihapus setelah pengujian; kini hanya tersisa satu konfigurasi.

## 32. Insiden: Odoo tidak dapat diakses

- Laporan: Odoo tidak bisa dibuka. Layanan `odoo18.service` berstatus **failed** sejak 12:46:54, tidak ada yang listen di port 8069.
- Rekonstruksi dari journal:
  - 12:46:52 sebuah kueri dijalankan lewat tombol **Tanya** di UI dan memakan **165 detik**.
  - Odoo mencatat `virtual real time limit (165/120s) reached` — batas `limit_time_real` bawaan adalah **120 detik**. Thread dianggap macet, stacktrace dibuang, lalu **server reload diri sendiri**.
  - Proses hasil reload mati saat import dengan `ModuleNotFoundError: No module named 'decorator'`.
  - Unit layanan memakai `Restart=no`, sehingga Odoo **tidak pernah bangkit sendiri** dan tetap mati ±10 menit sampai saya jalankan manual.
- Penyebab mendasar: inferensi CPU membutuhkan 40–170 detik per kueri, sedangkan PLAN hanya mengatur *HTTP timeout klien* (120–180 detik) dan **tidak mempertimbangkan batas waktu worker Odoo sendiri**. Batas 120 detik itu terlampaui sebelum timeout klien tercapai.
- Perbaikan (semuanya di sisi konfigurasi sistem):
  - `/etc/odoo18.conf`: `limit_time_real = 600`, `limit_time_cpu = 300`.
  - Drop-in systemd `/etc/systemd/system/odoo18.service.d/restart.conf`: `Restart=on-failure`, `RestartSec=5`.
  - `logfile` dipindah ke `/var/log/odoo18/odoo18.log` karena `/var/log/odoo` milik user `odoo` dan tidak dapat ditulis user `odoo18` — sebelumnya log hanya masuk stdout dan berkas log selalu 0 byte.
  - Konfigurasi lama dicadangkan ke `/etc/odoo18.conf.bak.*`.
- Verifikasi setelah perbaikan: layanan `active`, `Restart=on-failure`, `limit_time_real=600` efektif terbaca, logfile terbentuk dan terisi, `http://192.168.18.222:8069/web/login` merespons **303**, serta `llama-chat`, `llama-embed`, dan `postgresql` aktif.
- Tidak ada kueri yang tertinggal berstatus `running` — transaksi request yang terbunuh ikut ter-*rollback*, termasuk record lognya.

---

## Ringkasan terkini (per 2026-11-21, sore)

| Fase | Status |
|---|---|
| 0 — Fondasi & audit | ✅ |
| 1 — Akuisisi & kurasi data | ✅ (39 ayat, memakai AYT) |
| 2 — Infrastruktur & benchmark | ✅ |
| 3 — PostgreSQL | ✅ (indeks HNSW/GIN terpasang; `shared_buffers` masih tertunda) |
| 4 — Modul Odoo | ✅ |
| 5 — Ingestion, normalisasi, chunking | ✅ |
| 6 — Embedding otomatis | ✅ (39 vektor) |
| 7 — RAG & UI | 🟡 hampir selesai (router, RRF, konteks, ekspansi, prompt v2, konsol, teks asli, pilihan konfigurasi) |
| 8 — E2E & evaluasi formal | ⬜ belum |

**Angka kunci:** swap 10,7 GB → 1,4 GB · RAM ~50% · 7B 8,3 tok/s · 4B 12,3 tok/s · embedding 70 ms · prompt cache hemat ±25 detik/kueri · 39 chunk ter-embed dalam 29 detik · 9 transaksi kueri (33 hit) · 12 istilah ekspansi.

**Insiden yang sudah ditangani:** Odoo mati karena kueri 165 detik melewati `limit_time_real` 120 detik → limit dinaikkan ke 600/300, `Restart=on-failure` dipasang, log dipindah ke `/var/log/odoo18/`.

**Terbuka:** restart PostgreSQL untuk `shared_buffers` 1–2 GB · kunci API LAI (untuk mengganti AYT) · leksikon (ditunda) · uji formal Fase 8 · model 7B masih melewatkan ayat konteks yang tidak ditandai hasil pencarian.

## Kendala teknis yang sudah dilalui

- `sudo` gagal dari SSH (butuh TTY) → `sudo -S -p ''` dengan password via stdin.
- Kredensial tidak tersimpan (`/tmp` privat per perintah, home read-only) → disimpan di `.secrets/` workspace, mode 0600.
- `sudo` ditolak saat verifikasi akhir → helper dipanggil tanpa `--sudo`.
- `ValueError: Invalid format specifier` → `f"""...{"b64":"{b64}"}..."""` menafsirkan `:` sebagai format spec; hindari f-string untuk menyusun skrip remote.
- Perintah panjang terpotong batas waktu alat → dijalankan sebagai *background job*, hasil diambil lewat `job_output`.
- Model 20B tidak bisa dihentikan per unit → dilepas lewat `POST /models/unload`.
- Ekstensi `vector` ditolak non-superuser → dibuat superuser lebih dulu; hook modul memakai `IF NOT EXISTS`.
