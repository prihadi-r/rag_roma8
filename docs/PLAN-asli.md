# PLAN.md — RAG Roma 8 (Odoo + PostgreSQL `pgvector` + `llama.cpp`)

## 1. Tujuan & Ruang Lingkup
Membangun sistem *Retrieval-Augmented Generation* (RAG) lokal yang terintegrasi penuh di backend **Odoo** untuk studi eksposisi dan perbandingan tekstual **Roma 8 (ayat 1–39)**. Sistem menyandingkan tiga sumber utama secara paralel per ayat:
* **Bahasa Asli (Yunani Koine):** Robinson-Pierpont (*Byzantine Majority Textform*), dilengkapi data morfologi dan nomor Strong's.
* **Bahasa Inggris:** King James Version (KJV).
* **Bahasa Indonesia:** Lembaga Alkitab Indonesia (LAI - Terjemahan Baru).

## 2. Arsitektur Sistem & Batasan Hardware (16GB RAM CPU-Only)
Seluruh komponen (Odoo, PostgreSQL, dan `llama.cpp`) dirancang berjalan secara lokal tanpa GPU dengan anggaran memori ketat (**maksimal 6–8 GB RAM** untuk tumpukan AI agar total penggunaan RAM sistem tetap di bawah 85% tanpa menyentuh *swap*).
* **Database Layer:** PostgreSQL tunggal yang digunakan Odoo, diperkuat ekstensi **`pgvector`** (pencarian semantik), **`tsvector`** (pencarian kata kunci eksak), dan **`pg_trgm`** (*fuzzy matching*).
* **Inference & Embedding Layer:** Dua instance `llama-server` dari `llama.cpp` (satu untuk *chat completion*, satu untuk *embeddings*) dengan antarmuka API kompatibel OpenAI.
* **Optimasi CPU-Only:**
  * Menggunakan **RAG ketat (*Parent-Child Retrieval*)** alih-alih *full-context injection* agar *prompt evaluation* di CPU tetap cepat (±600–1.200 token per kueri).
  * Membatasi *context window* pada **4096** (maksimal 8192 token) dengan kuantisasi KV cache (`q8_0`) dan *prompt caching* aktif.
  * Mengatur jumlah *thread* `llama.cpp` sesuai jumlah **physical cores** CPU dan melonggarkan *HTTP timeout* klien Odoo (120–180 detik).

## 3. Pemilihan Model Lokal (`llama.cpp`)
* **Model LLM (Chat / Eksposisi):**
  * **Utama (Seimbang):** `Qwen 3 8B` atau `Qwen 2.5 7B Instruct` (`Q4_K_M`, estimasi ~5.0–5.5 GB RAM) — kuat pada Bahasa Indonesia, Inggris, dan kepatuhan instruksi *grounding*.
  * **Alternatif Ringan & Cepat:** `Qwen 3 4B` atau `Gemma 3 4B IT` (`Q4_K_M` / `Q5_K_M`, estimasi ~2.8–3.5 GB RAM) — direkomendasikan jika beban memori bersama Odoo dan PostgreSQL ketat.
* **Model Embedding (GGUF):**
  * **Utama:** `bge-m3` (`Q8_0`, 1024 dimensi, ~650 MB RAM) — unggul untuk pencarian lintas bahasa.
  * **Alternatif Ringan:** `multilingual-e5-base` (`Q8_0`, 768 dimensi, ~300–550 MB RAM).

## 4. Strategi Data & Chunking
* **Penyelarasan Paralel (*Verse-Aligned*):** Setiap ayat memuat teks Yunani asli (berdiakritik), teks Yunani ternormalisasi tanpa aksen (*stripped Greek*), KJV, LAI, dan anotasi morfologi/leksikon singkat.
* **Struktur *Parent-Child*:**
  * **Child (Unit Pencarian):** 1 ayat tunggal. *Embedding* difokuskan pada teks LAI, KJV, dan transliterasi/lemma Yunani (karena model embedding multibahasa kurang optimal pada teks Yunani politonik mentah).
  * **Parent (Unit Konteks):** 1 perikop utuh (misalnya: 8:1–11 Hidup oleh Roh, 8:12–17 Anak-anak Allah, 8:18–30 Pengharapan Kemuliaan, 8:31–39 Keyakinan Iman) atau jendela ±2 ayat agar alur logika Paulus tidak terputus.
* **Hybrid Search:** Menggabungkan *cosine similarity* (`pgvector`) dan *full-text search* (`tsvector`) menggunakan metode **Reciprocal Rank Fusion (RRF)**.

## 5. Arsitektur Custom Module Odoo (RAG Engine)
Modul kustom Odoo bertindak sebagai *self-contained RAG engine* tanpa memerlukan *orchestrator* eksternal:
* **Desain Model Relasional:**
  * **Master Konfigurasi LLM & RAG:** Endpoint `llama-server`, parameter model, *top-k*, *timeout*, dan templat *system prompt*.
  * **Master Perikop (*Parent*) & Master Ayat (*Child*):** Menggunakan relasi `Many2one` untuk seluruh entitas referensi (kitab, perikop, tema, kategori bahasa). Field `Selection` dibatasi hanya untuk pelacakan status pemrosesan (`draft`, `chunked`, `embedded`, `error`).
  * **Model Chunk & Vektor:** Menyimpan hasil *chunking*, *stripped Greek*, kolom `tsvector`, dan kolom `vector` (`pgvector`) yang diinisialisasi via *SQL hook* modul.
  * **Model Riwayat Kueri RAG:** Mencatat pertanyaan, ayat yang terambil, skor retrieval, latensi, dan respons LLM untuk audit.
* **Otomatisasi Embedding:** Dijalankan secara asinkron melalui *Scheduled Action* (`ir.cron`) secara *batch* untuk record berstatus `chunked` atau memiliki *dirty flag* (teks/metadata diubah), sehingga tidak memblokir *worker* HTTP Odoo.
* **Keamanan & Hak Akses:** Pemisahan peran **RAG User** (mengajukan kueri dan melihat riwayat sendiri) dan **RAG Manager** (mengelola master data, konfigurasi, impor, dan *re-embedding*) melalui `ir.model.access.csv` dan `ir.rule`.

## 6. Strategi Prompting, Guardrails & Evaluasi
* **Strict Grounding:** LLM wajib menjawab hanya berdasarkan teks yang diambil dari korpus, dengan *temperature* rendah (0.1–0.3).
* **Sitasi & Analisis Varian Tekstual:** Setiap jawaban wajib mencantumkan nomor ayat, kutipan kata persis, serta secara otomatis menyoroti perbedaan tekstual (*textual variants*) antara tradisi Byzantine (Robinson-Pierpont/KJV) dan teks eklektik (LAI), seperti pada Roma 8:1.
* **Evaluasi:** Diukur melalui ketepatan ayat yang terambil (*retrieval accuracy*), fidelitas kutipan teks Yunani/KJV/LAI, dan stabilitas penggunaan RAM/CPU.