# STATUS — RAG Roma 8

Diperbarui: 2026-11-21 · Host target: `192.168.18.222` (`nms`) · DB `rag_roma8`

> Rencana revisi: [PLAN.md](PLAN.md) · Daftar tugas: [TASK.md](TASK.md) · Jurnal: [PROGRESS.md](PROGRESS.md) · Dokumentasi modul: [docs/MODUL-ODOO.md](docs/MODUL-ODOO.md)

---

## Infrastruktur aktif

| Komponen | Status | Detail |
|---|---|---|
| PostgreSQL | ✅ | 16.15, cluster `main`, port 5432 |
| `pgvector` | ✅ | 0.6.0 (HNSW, cosine) — **tidak `trusted`** |
| `pg_trgm` | ✅ | 1.6 |
| DB `rag_roma8` | ✅ | owner `odoo18`, `vector` + `pg_trgm` aktif |
| `llama-embed` | ✅ | bge-m3 Q8_0, **1024 dim**, `127.0.0.1:8080` |
| `llama-chat` | ✅ | Qwen2.5-7B Q4_K_M, ctx 8192, KV q8_0, `127.0.0.1:8081` |
| `llama-chat-4b` | ⏸ | Qwen3-4B, disabled, cadangan di `:8092` |
| Odoo | ✅ | **18.2alpha1**, `/opt/odoo18` |
| Modul `rag_teologi` | ✅ | **17 tabel inti** + 3 tabel wizard sementara · 18 menu · 14 aksi · 25 view · 36 ACL · 4 rule |
| Data Roma 8 | ✅ | 4 perikop · 39 ayat · 21 varian · 39 chunk · **39 vektor** |
| Riwayat kueri | ✅ | **9 transaksi · 33 hit** |
| Ekspansi kueri | ✅ | **12 istilah** sinonim teologis |
| Batas waktu Odoo | ✅ | `limit_time_real=600`, `limit_time_cpu=300` |
| Pemulihan layanan | ✅ | `Restart=on-failure`, `RestartSec=5` |
| Log layanan | ✅ | `/var/log/odoo18/odoo18.log` |
| Panduan pengguna | ✅ | `USER_GUIDE.docx` — 15 halaman, 10 tangkapan layar asli |

---

## Progres per fase

### Fase 0 — Fondasi & Audit
- [x] SSH + sudo, audit server, identifikasi penyebab swap thrashing
- [x] Arsip rencana & tugas asli

### Fase 1 — Akuisisi & Kurasi Data
- [x] Sumber RP (public domain), KJV (public domain), **AYT** untuk Indonesia
- [x] Alignment 39 ayat, **verifikasi lulus**
- [x] Pembersihan: kurung KJV dipisah, `¶` → `paragraph_start`
- [x] Batas 4 perikop + 27 istilah teologis kunci
- [x] Dataset `data/roma8.json` + 4 berkas pendukung

**Sisa:** ganti `ind` ke TB/LAI bila kunci API diperoleh — tanpa ubah struktur.

### Fase 2 — Infrastruktur & Benchmark
- [x] `llama-server` chat & embedding sebagai unit systemd
- [x] Benchmark 4B vs 7B: 8,3 vs 12,3 tok/s
- [x] Uji beban memori gabungan (49,5%, swap dari RAG hanya 169 MB)

### Fase 3 — PostgreSQL
- [x] `pgvector` + `pg_trgm` terpasang, dimensi **1024** dikunci
- [x] Indeks HNSW + 3× GIN `tsvector` + GIN trigram **terpasang**
- [ ] `shared_buffers` 128 MB → 1–2 GB *(butuh restart PostgreSQL)*

### Fase 4 — Modul Odoo
- [x] Kerangka modul + manifest (`rag_teologi`)
- [x] 17 model inti + 3 wizard
- [x] SQL hook idempoten: kolom `vector`/`tsvector`, indeks
- [x] ACL **RAG User** / **RAG Manager** + 4 record rule
- [x] Deploy otomatis (`scripts/deploy_module.sh`)

### Fase 5 — Ingestion & Chunking
- [x] Wizard impor idempoten, galat dicatat per baris
- [x] Impor: 4 perikop, 39 ayat, 21 varian
- [x] Decoder morfologi **146/146 kode**
- [x] Chunking: **39 chunk**, `embed_text` + hash + token_est
- [x] Dirty flag merambat ke chunk

### Fase 6 — Embedding Otomatis
- [x] Klien HTTP dengan retry/backoff
- [x] `ir.cron` tiap 5 menit, batch 16
- [x] **39/39 chunk ter-embed** (1024 dim, 29 detik)
- [x] Tombol re-embed + jalur galat teruji

### Fase 7 — RAG & UI
- [x] Query Router (direct vs hybrid)
- [x] Hybrid RRF + tsquery OR
- [x] Context Builder: perikop hit-1 utuh, morfologi, varian, label sumber
- [x] **Ekspansi kueri** 12 istilah (8:29 naik dari dense-20 ke RRF-3)
- [x] Templat prompt **v2** (telusuri seluruh perikop)
- [x] Konsol Tanya RAG + tombol **Jalankan Kueri** pada riwayat
- [x] Tab **Teks Asli (Yunani)** mengikuti ayat yang dikutip
- [x] Pilihan **Pengaturan RAG** per kueri + pengaman model embedding
- [ ] (opsional) REST/JSON-RPC
- [ ] Search view & penyempurnaan UI

### Fase 8 — E2E & Evaluasi
- [ ] Uji install bersih dari nol
- [ ] Uji 10–15 pertanyaan dengan rubrik
- [ ] Penyetelan bobot RRF / prompt

---

## Catatan kunci

1. **Ekstensi `vector` tidak `trusted`** — sudah dibuat superuser di `rag_roma8`; untuk DB baru, harus dibuat superuser lebih dulu.
2. **`shared_buffers` masih 128 MB** — perlu 1–2 GB, tetapi butuh restart PostgreSQL (menunggu persetujuan).
3. **Batas waktu Odoo pernah mematikan layanan.** Kueri 165 detik melewati `limit_time_real` bawaan (120 detik) → Odoo reload diri → proses baru gagal → `Restart=no` membuatnya tetap mati. Sudah diperbaiki: limit 600/300, `Restart=on-failure`, log pindah ke `/var/log/odoo18/`.
4. **`addons_path` hanya `/opt/odoo18/addons`** (milik root) — deploy memakai sudo lewat skrip.
5. **Varian tekstual kini ditangani data + prompt v2**, bukan disimpulkan LLM. Uji 8:1 dan 8:29–30 lulus.
6. **Model 7B masih melewatkan ayat konteks** bila tidak ditandai hasil pencarian — batas model, bukan retrieval. Mitigasi: ekspansi kueri atau sebut nomor ayat (rute direct).
7. **Dataset di `/opt/odoo18/rag-data/`**, bukan di dalam modul — setiap deploy menghapus isi direktori modul.
