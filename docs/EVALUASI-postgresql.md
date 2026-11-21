# Evaluasi Sistem PostgreSQL — 192.168.18.222 (`nms@nms-zabbix`)

Tanggal: 2026-11-21 · Konteks: persiapan RAG Roma 8 (Odoo + pgvector + llama.cpp)

---

## 1. Ringkasan

| Item | Status |
|---|---|
| PostgreSQL | **16.15** (Ubuntu 24.04.5 LTS), cluster `main`, port 5432, **online** |
| `pgvector` | **BARU DIPASANG** → `postgresql-16-pgvector` **0.6.0-1** ✅ |
| `pg_trgm` | Tersedia (1.6) dan **sudah aktif** di DB `odoo18` & `demo` |
| Uji fungsional vektor | ✅ `vector(1024)`, cosine `<=>`, **Index Scan via HNSW**, GIN `tsvector` |
| Kapasitas hardware | i7-1260P (12C/16T), RAM 15,5 GB, swap 16 GB |
| **Kesehatan memori** | ⛔ **KRITIS** — swap terpakai 10,7 GB, `llama-server` ter-swap 9,4 GB |
| Disk | 386 GB / 466 GB terpakai (**88%**, sisa 56 GB) |
| Odoo | 18.0 di `/opt/odoo18`, service `odoo18.service`, port 8069 |

Kesimpulan singkat: **pgvector berhasil dipasang dan terbukti berfungsi**, tetapi sistem belum layak menjalankan RAG sesuai PLAN — bukan karena PostgreSQL, melainkan karena **swap thrashing** dan **`shared_buffers` yang terlalu kecil**.

**Tindak lanjut (2026-11-21):** swap thrashing sudah diatasi — model 20B dilepas (swap 10,7 GB → 1,4 GB), model pengganti dan layanan baru berjalan, dan database `rag_roma8` dibuat dengan `vector` + `pg_trgm` aktif. Rincian di [BENCHMARK-LLAMA.md](BENCHMARK-LLAMA.md) dan [../STATUS.md](../STATUS.md). Yang masih tertunda: tuning `shared_buffers` (butuh restart PostgreSQL).

---

## 2. Instalasi pgvector

```bash
sudo apt-get update
sudo apt-get install -y postgresql-16-pgvector
# → postgresql-16-pgvector 0.6.0-1 (amd64)
```

Verifikasi (dijalankan di database scratch `rag_ext_test`, lalu dibuang):

```
extname  | extversion
---------+------------
pg_trgm  | 1.6
vector   | 0.6.0

CREATE INDEX ON t USING hnsw (emb vector_cosine_ops);   -- OK
CREATE INDEX ON t USING gin  (txt);                     -- OK

Limit
  ->  Index Scan using t_emb_idx on t
        Order By: (emb <=> '[...]'::vector)            -- HNSW benar-benar dipakai
```

### Catatan versi

Paket Ubuntu 24.04 menyediakan **0.6.0**, bukan 0.8.x terkini. Yang hilang: `halfvec`, `sparsevec`, *iterative index scan*, dan perbaikan recall HNSW terbaru.

Untuk **39 ayat** Roma 8, ukuran korpus sangat kecil sehingga perbedaan ini **tidak relevan** — HNSW 0.6.0 sudah lebih dari cukup. Upgrade dari source (PGDG) hanya perlu bila nanti dipakai untuk korpus besar.

### ⚠️ Kendala penting: ekstensi butuh superuser

`/usr/share/postgresql/16/extension/vector.control` **tidak** memiliki `trusted = true`:

```
comment = 'vector data type and ivfflat and hnsw access methods'
default_version = '0.6.0'
module_pathname = '$libdir/vector'
relocatable = true          ← tidak ada baris "trusted = true"
```

Artinya `CREATE EXTENSION vector` **hanya bisa dijalankan superuser**. Odoo terhubung sebagai `odoo18` (**bukan** superuser), sehingga *SQL hook* di Fase 4 akan **gagal** `permission denied to create extension`.

Tiga jalan keluar:

| Opsi | Cara | Penilaian |
|---|---|---|
| **A** | Tambahkan `trusted = true` ke `vector.control`, lalu `systemctl reload postgresql` | **Direkomendasikan** — modul Odoo bisa self-init saat install/upgrade di DB mana pun, sesuai tuntutan Fase 4 |
| B | Superuser membuat ekstensi sekali per DB sebelum modul diinstal | Aman, tapi jadi prasyarat manual setiap DB baru |
| C | Jadikan `odoo18` superuser | ❌ Jangan — melanggar prinsip least privilege |

---

## 3. Database yang ada

| Database | Ukuran | Owner | Keterangan |
|---|---|---|---|
| `zabbix` | 1.328 MB | zabbix | monitoring, tidak disentuh |
| `demo` | 81 MB | odoo | sisa uji |
| `odoo18` | 48 MB | odoo18 | **DB Odoo produksi**, 63 modul terpasang |
| `template0/1`, `postgres` | ~7,5 MB | postgres | standar |

**Belum ada database khusus RAG.** Perlu keputusan: pakai `odoo18` atau buat DB bersih (mis. `rag_roma8`) agar eksperimen tidak mengotori produksi.

Ekstensi di `odoo18`: `plpgsql`, `pg_trgm`. **`vector` belum diaktifkan** di DB mana pun.

---

## 4. Konfigurasi PostgreSQL saat ini

| Parameter | Nilai | Rekomendasi | Alasan |
|---|---|---|---|
| `shared_buffers` | **128 MB** | 1.024–2.048 MB | terlalu kecil; HNSW + RRF butuh cache |
| `work_mem` | **4 MB** | 16–32 MB | query RRF melakukan beberapa sort/hash sekaligus |
| `maintenance_work_mem` | 64 MB | 256–512 MB | pembuatan indeks HNSW lebih cepat |
| `effective_cache_size` | 4 GB | 6–8 GB | perkiraan planner, bukan alokasi nyata |
| `random_page_cost` | 4 | 1.1 | penyimpanan SSD |
| `max_connections` | 100 | biarkan | cukup |
| `max_parallel_workers` | 8 | 4 | hindari rebutan CPU dengan llama.cpp |
| `listen_addresses` | `*` | `localhost` | ⚠️ port 5432 terbuka ke LAN |
| `shared_preload_libraries` | kosong | kosong | pgvector **tidak** butuh preload — aman |

`pg_hba.conf`: `local ... peer` untuk semua user; `host 127.0.0.1/32 scram-sha-256`. Artinya `sudo -u postgres psql` jalan lokal, dan Odoo masuk lewat TCP dengan password.

---

## 5. ⛔ Temuan kritis: swap thrashing

```
Mem:   total 15.498 MB   used 8.572 MB   available 6.925 MB
Swap:  total 16.383 MB   used 10.696 MB   (65% penuh)

PID 718549  llama-server  VmRSS 2.264 MB   VmSwap 9.455 MB   ← 9,4 GB di swap!
```

`llama-server` (pid 718549) memuat **gpt-oss-20b-Q4_K_M (12 GB)** dengan `--ctx-size 32768`. Model ini jauh melampaui anggaran PLAN (maksimal 6–8 GB untuk tumpukan AI). Akibatnya **9,4 GB model terlempar ke swap**.

Konsekuensi praktis: setiap token generation harus membaca bobot dari disk. Kecepatan inference akan jatuh ke orde **jauh di bawah 1 token/detik** — bukan karena CPU, tapi karena swap.

Layanan yang sedang berjalan:

| Service | Port | Bind | Model / Catatan |
|---|---|---|---|
| `llama-server` | 52017 | 127.0.0.1 | `gpt-oss-20b-Q4_K_M`, threads 12, status `ok` |
| `llama-server` | 7070 | **0.0.0.0** | multi-model manager, `--api-key` (⚠️ **nilai disunting**; kunci asli ada di argv proses) |
| `ollama` | 11434 | semua interface | ollama serve |
| `odoo18` | 8069 | 0.0.0.0 | Odoo 18 |
| `mysql` | - | - | Zabbix, tidak terkait |

---

## 6. Model yang tersedia di `/home/nms/llama.cpp/models/`

| Model | Ukuran | Peran potensial |
|---|---|---|
| `gpt-oss-20b-Q4_K_M` | 12 GB | ❌ terlalu besar, penyebab swap |
| `Qwen3-14B-Q4_K_M` | 9,0 GB | ❌ di atas anggaran |
| `DeepSeek-R1-Distill-Qwen-14B` | 9,0 GB | ❌ di atas anggaran |
| `Qwen1.5-MoE-A2.7B-Chat` | 9,5 GB | ❌ MoE, kompleks |
| `Qwen2.5-Coder-7B-Instruct-Q4_K_M` | 4,7 GB | ⚠️ *coder*, bukan untuk eksposisi |
| `nomic-embed-text-v1.5.Q8_0` | 146 MB | ⚠️ embedding, **768 dim, lemah untuk Bahasa Indonesia** |

**`bge-m3` belum ada** — padahal itu model embedding utama di PLAN (1024 dim, unggul lintas bahasa). Ini gap yang harus ditutup di Fase 2.

Kabar baik: `llama.cpp` sudah **build 12032 (0.8.0-dev)**, mendukung `--embeddings`, `--flash-attn`, `--jinja`, dan mode multi-model di port 7070.

---

## 7. Odoo 18

```
db_host = localhost      db_user = odoo18
addons_path = /opt/odoo18/addons          ← hanya satu path, milik root
logfile = /var/log/odoo/odoo18.log
```

Implikasi untuk Fase 4: modul kustom **tidak bisa** langsung ditulis ke `/opt/odoo18/addons` (butuh sudo). Pilihan: deploy via sudo, atau tambahkan path baru di `odoo18.conf` (mis. `/opt/odoo18/custom-addons`) yang dimiliki user Odoo.

---

## 8. Rekomendasi berurutan

1. **Hentikan `llama-server` 20B** (pid 718549) → swap turun drastis, sistem kembali responsif.
2. **Turunkan model ke kelas 4B–8B** sesuai PLAN; jalankan ulang benchmark setelah swap bersih, bukan sebelum — angka benchmark saat ini tidak valid.
3. **Unduh `bge-m3` Q8_0** (~650 MB) untuk endpoint embedding 1024 dim.
4. **Aktifkan `vector`** di DB target — pilih opsi A (`trusted = true`) agar modul Odoo bisa self-init.
5. **Tuning PostgreSQL**: `shared_buffers` 1–2 GB, `work_mem` 16–32 MB, `random_page_cost` 1.1. Lakukan **setelah** RAM lega.
6. **Keamanan**: `listen_addresses = localhost`, pindahkan API key llama.cpp keluar dari argv.
7. **Disk 88%** — sisa 56 GB cukup untuk proyek ini, tapi pantau.
8. **Putuskan DB**: pakai `odoo18` atau DB baru `rag_roma8`.

---

## 9. Reproduksi

Helper SSH dan audit dapat diulang dengan:

```bash
python3 scripts/rrun.py 'perintah'          # read-only, user nms
python3 scripts/rrun.py --sudo 'perintah'   # sudo via stdin
python3 scripts/rrun.py -s <<'EOF'          # skrip multi-baris
...
EOF
```

Kredensial tersimpan di `.secrets/rsh_pass` (mode 0600, masuk `.gitignore`).
