# TASK.md — Implementasi RAG Roma 8 (Odoo + PostgreSQL `pgvector` + `llama.cpp`)

## Fase 1: Akuisisi & Kurasi Data
- [ ] Kumpulkan teks lengkap Roma 8:1–39 versi Robinson-Pierpont (beserta kode parsing morfologi dan nomor Strong's).
- [ ] Kumpulkan teks lengkap Roma 8:1–39 versi KJV dan LAI (Terjemahan Baru).
- [ ] Bersihkan teks (*encoding* UTF-8 konsisten, hapus catatan kaki/nomor halaman yang tidak relevan).
- [ ] Lakukan penyelarasan (*alignment*) 1-ke-1 untuk ke-39 ayat dan verifikasi kelengkapan teks secara manual.
- [ ] Tentukan batas perikop Roma 8 (*parent*) dan siapkan daftar istilah teologis kunci per ayat.

## Fase 2: Setup Infrastruktur Lokal & Benchmark CPU (16GB RAM)
- [ ] Siapkan `llama-server` untuk layanan LLM (*chat completion*) dengan *context window* 4096–8192, kuantisasi KV cache `q8_0`, *prompt caching* aktif, dan *thread* sesuai *physical cores* CPU.
- [ ] Siapkan `llama-server` untuk layanan *embedding* dengan model `bge-m3` (`Q8_0`) atau `multilingual-e5-base` (`Q8_0`).
- [ ] Lakukan *benchmark* kecepatan (*prompt eval* & *token/sec*) antara kandidat **4B** vs **7B/8B** (`Q4_K_M`) pada mesin target.
- [ ] Uji beban memori secara bersamaan (Odoo + PostgreSQL + kedua instance `llama-server`) untuk memastikan total RAM tetap di bawah 85% tanpa *swap*.

## Fase 3: Setup PostgreSQL (`pgvector` & Full-Text Search)
- [ ] Instal dan aktifkan ekstensi `pgvector` dan `pg_trgm` pada database PostgreSQL target Odoo.
- [ ] Kunci dimensi kolom vektor sesuai model embedding terpilih (`1024` untuk `bge-m3` atau `768` untuk `multilingual-e5-base`).
- [ ] Rancang skema indeks `HNSW` (untuk kolom vektor) dan `GIN` (untuk kolom `tsvector` pada teks LAI, KJV, dan *stripped Greek*).

## Fase 4: Inisialisasi Custom Module Odoo & Skema Data
- [ ] Buat struktur kerangka *custom module* Odoo beserta manifest dan dependensi dasarnya.
- [ ] Definisikan model Master Konfigurasi `llama.cpp`, Master Perikop (*Parent*), Master Ayat (*Child*), Model Chunk/Vektor, dan Model Riwayat Kueri.
- [ ] Terapkan aturan arsitektur: gunakan relasi `Many2one` untuk seluruh data master/referensi dan batasi `Selection` hanya untuk field status (`state`).
- [ ] Siapkan mekanisme inisialisasi SQL (*init/post-init hook*) agar ekstensi `pgvector`, kolom `vector`, kolom `tsvector`, dan seluruh indeks otomatis terbentuk saat modul diinstal atau di-*upgrade*.
- [ ] Konfigurasikan hak akses grup **RAG User** dan **RAG Manager** pada `ir.model.access.csv` dan `ir.rule`.

## Fase 5: Ingestion, Normalisasi & Chunking Engine di Odoo
- [ ] Buat *Wizard* impor data di backend Odoo untuk memuat dataset paralel Roma 8 beserta metadata morfologi.
- [ ] Implementasikan normalisasi teks otomatis saat impor untuk membentuk kolom *stripped Greek* (tanpa aksen/diakritik).
- [ ] Implementasikan *Chunking Engine* untuk menyusun unit *child* (ayat) yang terhubung ke *parent* (perikop), lalu mengubah status record menjadi `chunked`.
- [ ] Tambahkan mekanisme *dirty flag* otomatis setiap kali teks ayat, terjemahan, atau metadata morfologi diedit.

## Fase 6: Otomatisasi Embedding (`ir.cron`)
- [ ] Bangun layanan klien HTTP internal di Odoo untuk berkomunikasi dengan endpoint `/v1/embeddings` milik `llama.cpp` (lengkapi dengan *timeout*, *retry*, dan pencatatan *error*).
- [ ] Buat *Scheduled Action* (`ir.cron`) untuk memproses record berstatus `chunked` atau *dirty* secara *batch*, menyimpan vektor ke kolom `pgvector`, dan mengubah status menjadi `embedded`.
- [ ] Sediakan tombol aksi manual (*Re-embed Selected*) pada tampilan *List* dan *Form* bagi **RAG Manager**.

## Fase 7: Pemrosesan RAG & Antarmuka Pengguna Odoo
- [ ] Implementasikan *Query Router* di backend Odoo untuk membedakan pencarian nomor ayat spesifik (*direct lookup*) dengan pencarian konseptual (*hybrid search*).
- [ ] Implementasikan metode *Hybrid Search* via SQL di Odoo yang menggabungkan skor `pgvector` dan `tsvector` menggunakan *Reciprocal Rank Fusion* (RRF).
- [ ] Implementasikan *Context Builder* yang otomatis melampirkan konteks perikop (*parent*) dan *system prompt* eksposisi sebelum memanggil `/v1/chat/completions` (dengan *HTTP timeout* 120–180 detik).
- [ ] Buat tampilan UI Odoo (Menu, *List View*, *Form View*, *Search View*, dan konsol tanya-jawab RAG) untuk pengelolaan data dan pengujian langsung.
- [ ] (Opsional) Ekspos layanan RAG melalui endpoint REST/JSON-RPC Odoo untuk konsumsi aplikasi eksternal.

## Fase 8: Pengujian End-to-End & Evaluasi
- [ ] Uji proses *install* dan *upgrade* modul di Odoo untuk memastikan tidak ada konflik antara ORM Odoo dan kolom `pgvector`.
- [ ] Uji eksekusi *Wizard* impor, *Chunking Engine*, dan `ir.cron` untuk seluruh 39 ayat Roma 8 (termasuk skenario *re-embedding* parsial).
- [ ] Buat 10–15 pertanyaan uji (mencakup pencarian kata Yunani, perbandingan terjemahan KJV vs LAI, varian tekstual Roma 8:1, dan alur argumen Paulus).
- [ ] Evaluasi hasil jawaban berdasarkan akurasi ayat terambil, fidelitas kutipan teks asli, dan waktu respons CPU, lalu lakukan penyetelan akhir pada bobot RRF atau *system prompt*.