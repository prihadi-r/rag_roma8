# DESAIN SKEMA RAG Roma 8 — "Collection" & Struktur Field

Status: **diimplementasikan** di modul `rag_teologi` (Odoo **18.2alpha1**) · Lihat [MODUL-ODOO.md](MODUL-ODOO.md) untuk penyimpangan nyata

Target: Odoo 18 + PostgreSQL 16.15 + `pgvector` 0.6.0
Terkait: [PLAN.md](../PLAN.md) §6 · [SUMBER-TEKS.md](SUMBER-TEKS.md) · [STATUS.md](../STATUS.md)

---

## 1. Apa arti "collection" di tumpukan ini

Di vector database komersial (Pinecone, Chroma, Weaviate), *collection* adalah wadah terpisah dengan indeks sendiri. Di tumpukan kita **tidak ada lapisan itu** — PostgreSQL adalah vector database-nya. Padanannya:

> **1 collection = 1 tabel + kolom `vector` + indeks HNSW-nya.**

Keputusan penting: kita **hanya membuat satu collection pencarian**, yaitu `rag_chunk`. Alasannya:

- Satu jenis unit pencarian (ayat) menghindari kebutuhan menggabungkan skor antar-collection.
- Perikop, varian, dan leksikon **bukan** target pencarian vektor — mereka konteks yang di-*join*, bukan yang di-embed.
- Bila nanti perlu embedding tingkat perikop, tambahkan **baris** di `rag_chunk` dengan `chunk_kind_id` berbeda, bukan tabel baru. Skema tetap, query tetap.

---

## 2. Peta relasi

```
                    ┌──────────────────┐
                    │  rag_embedding_  │
                    │  model           │
                    └────────┬─────────┘
                             │
┌──────────────┐   ┌─────────▼────────┐   ┌──────────────────┐
│  rag_book    │──▶│   rag_pericope   │◀──│  rag_chunk_kind  │
└──────┬───────┘   └────────┬─────────┘   └──────────────────┘
       │                    │
       │           ┌────────▼─────────┐
       └──────────▶│    rag_verse     │◀──────┐
                   └───┬────────┬─────┘       │
                       │        │             │
        ┌──────────────▼──┐  ┌──▼───────────┐ │
        │   rag_chunk     │  │ rag_variant  │ │
        │  (collection)   │  └──┬────────┬──┘ │
        │  vector + fts   │     │        │    │
        └───┬─────────┬───┘  ┌──▼──────┐ │    │
            │         │      │rag_     │ │    │
   ┌────────▼──┐  ┌───▼────┐ │witness  │ │    │
   │rag_query_ │  │rag_    │ └─────────┘ │    │
   │hit        │  │query_  │ ┌───────────▼─┐ │
   └────┬──────┘  │log     │ │rag_variant_ │ │
        │         └───┬────┘ │type         │ │
        └─────────────┘      └─────────────┘ │
                   ┌──────────────────────────┘
                   │
            ┌──────▼──────────┐    ┌──────────────────┐
            │  rag_config     │───▶│ rag_prompt_      │
            └─────────────────┘    │ template         │
                                   └──────────────────┘
            ┌──────────────────┐
            │ rag_import_      │
            │ batch            │
            └──────────────────┘
```

---

## 3. Aturan desain yang dipatuhi

| Aturan (dari PLAN §6) | Penerapan |
|---|---|
| `Many2one` untuk semua referensi | `book_id`, `pericope_id`, `witness_id`, `variant_type_id`, `chunk_kind_id`, `embedding_model_id`, `route_id`, dan `prompt_template_id` **pada riwayat kueri** (bukan pada konfigurasi) |
| `Selection` **hanya** untuk status | Hanya field `state` pada `rag_verse`, `rag_chunk`, `rag_query_log`, `rag_import_batch` |
| Kolom `vector`/`tsvector` di luar ORM | Dibuat lewat SQL hook; dibaca/tulis lewat helper `cr.execute` |
| Nama tabel | Eksplisit `_table = 'rag_*'` (bukan awalan modul) — proyek tunggal, nama pendek lebih terbaca. **Konsekuensi:** jangan pasang dua modul RAG sekaligus |

---

## 4. Tabel referensi (master enumerasi)

Semua berbentuk sama: `id, code, name, sequence, active`. Kecil, tapi memenuhi aturan "referensi lewat relasi, bukan `Selection`".

| Tabel | Isi awal |
|---|---|
| `rag_chunk_kind` | `verse` (1 ayat), `window_3` (±1 ayat), `pericope` (perikop utuh) |
| `rag_witness` | `BYZ` (Robinson-Pierpont), `NA` (Nestle-Aland), `ECM` (Editio Critica Maior), `TR` |
| `rag_variant_type` | `omission`, `addition`, `substitution`, `transposition` |
| `rag_query_route` | `direct` (nomor ayat), `hybrid` (konseptual) |

---

## 5. Tabel inti

### 5.1 `rag_embedding_model`

Mencatat model mana yang menghasilkan vektor. Tanpa ini, mengganti model di tengah proyek akan mencampur vektor berdimensi/ruang berbeda tanpa jejak.

| Field | Tipe | Keterangan |
|---|---|---|
| `name` | char, required | `bge-m3-Q8_0` |
| `provider` | m2o `rag_provider` → char (`llamacpp`) | atau char langsung |
| `endpoint` | char | `http://127.0.0.1:8080/v1/embeddings` |
| `dimensions` | integer, required | **1024** |
| `quantization` | char | `Q8_0` |
| `normalized` | boolean | true — bge-m3 sudah L2=1.0 |
| `active` | boolean | hanya satu aktif dipakai cron |

**Constraint:** `unique(dimensions, name)`; indeks parsial `WHERE active` di `rag_config`.

### 5.2 `rag_config`

> **Revisi implementasi:** `prompt_template_id` **dihapus** dari tabel ini. Templat prompt berdiri sendiri; pengguna memilihnya per kueri pada konsol, dan pilihan itu dicatat di `rag_query_log.prompt_template_id`.

Singleton konfigurasi. Satu baris aktif.

| Field | Tipe | Default | Catatan |
|---|---|---|---|
| `name` | char | — | "Roma 8 — lokal" |
| `chat_base_url` | char | `http://127.0.0.1:8081/v1` | |
| `chat_model` | char | `qwen2.5-7b-instruct` | |
| `embed_base_url` | char | `http://127.0.0.1:8080/v1` | |
| `embedding_model_id` | m2o, required | bge-m3 | |
| `top_k_dense` | integer | 20 | kandidat vektor |
| `top_k_fts` | integer | 20 | kandidat full-text |
| `rrf_k` | integer | 60 | konstanta RRF |
| `top_k_final` | integer | 5 | masuk konteks |
| `temperature` | float | 0.2 | |
| `max_tokens` | integer | 600 | |
| `context_budget_chars` | integer | 6000 | ±1.500 token |
| `timeout_chat_s` | integer | 180 | |
| `timeout_embed_s` | integer | 30 | |
| `active` | boolean | true | |

**Constraint:** `unique(active) WHERE active` → mustahil ada dua konfigurasi aktif.

### 5.3 `rag_prompt_template`

Templat berversi, karena kualitas jawaban sangat bergantung pada instruksi (lihat kegagalan varian tekstual).

| Field | Tipe | Catatan |
|---|---|---|
| `name` | char, required | `eksposisi-grounding-v1` |
| `role` | char | `system` / `context_builder` |
| `body` | text | berisi placeholder `{{context}}`, `{{variants}}` |
| `version` | integer | naik setiap revisi |
| `active` | boolean | |

**Constraint:** `unique(name, version)`.

### 5.4 `rag_book`

| Field | Tipe | Catatan |
|---|---|---|
| `code` | char, required, unique | `ROM` |
| `name_id` / `name_en` / `name_gr` | char | `Roma` / `Romans` / `Πρὸς Ῥωμαίους` |
| `chapter_count` | integer | 16 |

### 5.5 `rag_pericope` — **parent** (unit konteks)

| Field | Tipe | Catatan |
|---|---|---|
| `book_id` | m2o, required | |
| `chapter` | integer, required | 8 |
| `verse_start` / `verse_end` | integer, required | 1 / 11 |
| `title_id` | char | "Hidup oleh Roh" |
| `title_en` | char | |
| `summary_id` | text | ringkasan 2–3 kalimat untuk konteks |
| `sequence` | integer | urutan dalam pasal |
| `state` | selection | `draft`, `ready`, `error` |

**Constraint:** `unique(book_id, chapter, verse_start, verse_end)`

Perikop rencana: 8:1–11 · 8:12–17 · 8:18–30 · 8:31–39.

### 5.6 `rag_verse` — **child** (kebenaran kanonik)

Sumber tunggal teks. Tidak menyimpan vektor maupun `tsvector`.

| Field | Tipe | Catatan |
|---|---|---|
| `book_id` | m2o, required, index | |
| `pericope_id` | m2o, index | parent konteks |
| `chapter` | integer, required | |
| `verse_no` | integer, required | |
| `ref_label` | char, compute, store | `Roma 8:1` |
| `greek_accented` | text | dari `ccat/no-variants` |
| `greek_stripped` | text | dari `strongs/with-parsing` |
| `kjv` | text | kurung siku `[...]` dibuang |
| `lai` | text | dari API LAI |
| `lai_attribution` | char | **wajib**: `Dikutip dari ALKITAB (TB) © LAI 1974` |
| `words` | json | `[{surface, stripped, strongs, morph, lemma, translit}]` |
| `word_count` | integer, compute, store | dari `len(words)` |
| `apparatus_raw` | text | potongan `{NA … > - }` apa adanya |
| `state` | selection | `draft`, `chunked`, `embedded`, `error` |
| `dirty` | boolean, default true, index | |
| `content_hash` | char(64) | sha256 teks gabungan — pendeteksi perubahan |
| `source_note` | text | asal-usul & tanggal unduh |

**Constraints:** `unique(book_id, chapter, verse_no)`; `check(verse_no >= 1)`.

> `state` di sini mencerminkan status **anak**; `dirty` terpisah karena satu ayat bisa *embedded* tetapi kemudian diedit.

### 5.7 `rag_chunk` — **collection pencarian**

Satu baris = satu unit yang di-embed dan dicari. Teks **sengaja didenormalisasi** dari `rag_verse`, karena kolom `GENERATED tsvector` tidak bisa merujuk tabel lain. Konsistensi dijaga oleh proses chunking (bukan oleh manusia).

| Field | Tipe | Catatan |
|---|---|---|
| `verse_id` | m2o, required, cascade, index | |
| `pericope_id` | m2o, index | untuk *context builder* tanpa join ganda |
| `chunk_kind_id` | m2o, required | default `verse` |
| `embedding_model_id` | m2o | wajib saat `embedded` |
| `seq` | integer | urutan dalam perikop |
| `lai_text` | text | salinan untuk FTS |
| `kjv_text` | text | salinan untuk FTS |
| `greek_stripped` | text | salinan untuk FTS |
| `lexeme_text` | text | lema + Strong's, menambah daya cari |
| `embed_text` | text, required | **komposisi** yang di-embed, lihat §6 |
| `embed_hash` | char(64) | sha256 `embed_text`; jika beda → wajib re-embed |
| `token_est` | integer | perkiraan token `embed_text` |
| `state` | selection | `draft`, `chunked`, `embedded`, `error` |
| `dirty` | boolean, default true, index | |
| `retry_count` | integer, default 0 | untuk backoff cron |
| `last_error` | text | |
| `embedded_at` | datetime | |
| **`embedding`** | `vector(1024)` | **non-ORM**, dibuat SQL hook |
| **`fts_id`** | `tsvector` generated | dari `lai_text` |
| **`fts_en`** | `tsvector` generated | dari `kjv_text` |
| **`fts_gr`** | `tsvector` generated | dari `greek_stripped` + `lexeme_text` |

**Constraints:** `unique(verse_id, chunk_kind_id)`.

### 5.8 `rag_variant` — varian tekstual sebagai data

Ini yang menggantikan "LLM menyimpulkan varian" dengan "sistem menyajikan varian".

| Field | Tipe | Catatan |
|---|---|---|
| `verse_id` | m2o, required, cascade | |
| `seq` | integer | urutan klausa |
| `clause_ref` | char | `8:1b` |
| `witness_id` | m2o `rag_witness` | pihak yang membaca demikian |
| `variant_type_id` | m2o `rag_variant_type` | `omission` untuk kasus 8:1 |
| `byz_text` | text | bacaan Byzantine |
| `other_text` | text | bacaan saksi lain (`-` bila kosong) |
| `apparatus_note` | text | `{NA μὴ κατὰ σάρκα… > - }` |
| `is_significant` | boolean | tampilkan di jawaban |
| `source` | char | `RP2018 apparatus` |

**Contoh isi untuk 8:1:** `witness=NA`, `variant_type=omission`, `byz_text` = klausa penuh, `other_text` = `-`.

### 5.9 `rag_query_log`

| Field | Tipe | Catatan |
|---|---|---|
| `name` | char | 60 karakter pertama pertanyaan |
| `question` | text, required | |
| `route_id` | m2o `rag_query_route` | `direct` / `hybrid` |
| `config_id` | m2o | snapshot konfigurasi saat itu |
| `params` | json | `{top_k_dense, top_k_fts, rrf_k, temperature}` |
| `answer` | text | |
| `citations` | json | `[{verse, quote}]` |
| `latency_ms` | integer | total |
| `stage_ms` | json | `{embed, search, prompt, generate}` |
| `prompt_tokens` / `completion_tokens` | integer | dari `timings` |
| `state` | selection | `success`, `error` |
| `error` | text | |
| `user_id` | m2o `res.users`, default current | untuk record rule |

### 5.10 `rag_query_hit`

Dipisah dari log agar bisa dianalisis: *apakah ayat yang benar terambil, dan pada peringkat berapa?* Inilah dasar evaluasi Fase 8.

| Field | Tipe | Catatan |
|---|---|---|
| `query_id` | m2o, required, cascade, index | |
| `chunk_id` | m2o, required, index | |
| `rank_dense` / `rank_fts` | integer | `NULL` bila tidak masuk kandidat |
| `score_dense` | double | cosine similarity |
| `score_fts` | double | `ts_rank_cd` |
| `rrf_score` | double | hasil fusi |
| `position` | integer | urutan akhir |
| `injected` | boolean | masuk konteks LLM atau tidak |

### 5.11 `rag_import_batch`

| Field | Tipe | Catatan |
|---|---|---|
| `name` | char | `RP-KJV-LAI 2026-11-21` |
| `source` | char | `byztxt`, `ebible`, `lai-api` |
| `file_hash` | char(64) | |
| `rows_total` / `rows_ok` / `rows_error` | integer | |
| `log` | text | |
| `state` | selection | `draft`, `running`, `done`, `error` |

---

## 6. Komposisi `embed_text` — keputusan yang menentukan kualitas

PLAN §4 menyatakan model embedding multibahasa lemah pada Yunani politonik mentah. Karena itu `embed_text` **bukan** sekadar gabungan tiga teks:

```
LAI: Demikianlah sekarang tidak ada penghukuman bagi mereka yang ada di dalam Kristus Yesus.
KJV: There is therefore now no condemnation to them which are in Christ Jesus.
YUNANI (transliterasi): ouden ara nyn katakrima tois en christō Iēsou
LEMA: οὐδείς | ἄρα | νῦν | κατάκριμα | ὁ | ἐν | Χριστός | Ἰησοῦς
GLOSS: none/therefore/now/condemnation/the/in/Christ/Jesus
```

Aturan:

1. **Yunani berdiakritik tidak di-embed** — hanya transliterasi + lema.
2. **Gloss Strong's disertakan** agar pertanyaan berbahasa Indonesia ("penghukuman") dapat bertemu kata Yunani.
3. Urutan tetap dan deterministik, karena `embed_hash` bergantung padanya.
4. `embed_text` disimpan apa adanya, sehingga vektor bisa direproduksi dan diaudit.

**Implementasi aktual (Fase 5):** enam baris — `ID`, `EN`, `YUNANI`, `TRANS`, `LEMA`, `GLOSS`. Lema dan glos diambil dari **Strong's Greek Dictionary** (public domain), bukan dari leksikon berlisensi. Glos dibatasi dua pengertian pertama per kata agar tidak mendominasi vektor. Rincian: [MODUL-ODOO.md](MODUL-ODOO.md) §11.

---

## 7. Indeks

| Tabel | Indeks | Tipe | Alasan |
|---|---|---|---|
| `rag_verse` | `unique(book_id, chapter, verse_no)` | btree | integritas |
| `rag_verse` | `(pericope_id)` | btree | join konteks |
| `rag_verse` | `(dirty) WHERE dirty` | btree parsial | cron hanya memindai yang kotor |
| `rag_chunk` | `embedding` | **HNSW** `vector_cosine_ops (m=16, ef_construction=64)` | pencarian semantik |
| `rag_chunk` | `fts_id` | **GIN** | kata Indonesia |
| `rag_chunk` | `fts_en` | **GIN** | kata Inggris (KJV) |
| `rag_chunk` | `fts_gr` | **GIN** | kata Yunani tanpa aksen + lema |
| `rag_chunk` | `greek_stripped gin_trgm_ops` | **GIN pg_trgm** | toleransi salah ketik aksen |
| `rag_chunk` | `(dirty) WHERE dirty` | btree parsial | antrean embedding |
| `rag_query_hit` | `(query_id)` | btree | laporan evaluasi |

**Ukuran terukur:** kolom `vector(1024)` = **4.100 byte/baris**. Untuk 39 ayat ≈ 160 KB. Seluruh tabel + indeks masih di bawah 1 MB — HNSW praktis instan, `ef_search` tidak perlu di-tuning.

---

## 8. Query inti

### 8.1 Direct lookup (jalur varian & nomor ayat)

```sql
SELECT v.ref_label, v.greek_accented, v.kjv, v.lai,
       coalesce(json_agg(json_build_object(
         'witness', w.code, 'type', vt.code,
         'byz', va.byz_text, 'other', va.other_text)) FILTER (WHERE va.id IS NOT NULL), '[]') AS variants
FROM rag_verse v
LEFT JOIN rag_variant va      ON va.verse_id = v.id
LEFT JOIN rag_witness w       ON w.id = va.witness_id
LEFT JOIN rag_variant_type vt ON vt.id = va.variant_type_id
WHERE v.book_id = %(book)s AND v.chapter = 8 AND v.verse_no = ANY(%(verses)s)
GROUP BY v.id
ORDER BY v.verse_no;
```

### 8.2 Hybrid search dengan RRF (terverifikasi jalan)

```sql
WITH dense AS (
  SELECT c.id, row_number() OVER (ORDER BY c.embedding <=> %(qvec)s) AS rnk
  FROM rag_chunk c
  WHERE c.state = 'embedded'
  ORDER BY c.embedding <=> %(qvec)s
  LIMIT %(k_dense)s
), fts AS (
  SELECT c.id,
         row_number() OVER (
           ORDER BY ts_rank_cd(c.fts_id, q) + ts_rank_cd(c.fts_en, q) + ts_rank_cd(c.fts_gr, q) DESC
         ) AS rnk
  FROM rag_chunk c, plainto_tsquery('simple', %(qtext)s) q
  WHERE c.fts_id @@ q OR c.fts_en @@ q OR c.fts_gr @@ q
  LIMIT %(k_fts)s
)
SELECT coalesce(d.id, f.id) AS chunk_id,
       d.rnk AS rank_dense, f.rnk AS rank_fts,
       (1.0/(%(rrf_k)s + coalesce(d.rnk, 1000))
      + 1.0/(%(rrf_k)s + coalesce(f.rnk, 1000))) AS rrf
FROM dense d FULL OUTER JOIN fts f ON d.id = f.id
ORDER BY rrf DESC
LIMIT %(k_final)s;
```

Catatan dari uji: `'simple'` **cukup** untuk Yunani tanpa aksen — `κατακριμα` terindeks dan ditemukan. Tidak perlu konfigurasi teks khusus.

### 8.3 Konteks dibangun oleh Odoo, bukan SQL

Setelah RRF, `Context Builder` mengambil `pericope_id` dari chunk teratas, lalu menyusun:

```
[PERIKOP 8:1–11 — Hidup oleh Roh]
<ringkasan 2–3 kalimat>

[AYAT TERAMBIL]
Roma 8:1
  Yunani : Οὐδὲν ἄρα νῦν κατάκριμα …
  KJV    : There is therefore now no condemnation …
  LAI    : Demikianlah sekarang tidak ada penghukuman …
  Varian : [NA menghilangkan: μὴ κατὰ σάρκα περιπατοῦσιν ἀλλὰ κατὰ πνεῦμα]
```

Baris **Varian** wajib hadir bila ada — inilah perbaikan atas kegagalan sebelumnya.

---

## 9. Mesin status

```
rag_verse:  draft ──chunking──▶ chunked ──embedding──▶ embedded
                ▲                                          │
                └────────────── edit (dirty=true) ◀────────┘
                                  gagal ──▶ error
```

- `dirty` **tidak** menggantikan `state`; keduanya berbeda makna.
- Mengubah `greek_accented`/`kjv`/`lai`/`words` → trigger menandai `dirty=true` pada verse terkait.
- Cron memproses `state='chunked' OR dirty=true` secara batch.
- Setelah embed sukses: `dirty=false`, `state='embedded'`, `embed_hash` disimpan.

---

## 10. DDL untuk kolom non-ORM

Tidak ditangani ORM karena tipenya tidak dikenal Odoo.

```sql
-- dijalankan oleh SQL hook modul (init + upgrade)
ALTER TABLE rag_chunk ADD COLUMN IF NOT EXISTS embedding vector(1024);

ALTER TABLE rag_chunk ADD COLUMN IF NOT EXISTS fts_id tsvector
  GENERATED ALWAYS AS (to_tsvector('simple', coalesce(lai_text,''))) STORED;

ALTER TABLE rag_chunk ADD COLUMN IF NOT EXISTS fts_en tsvector
  GENERATED ALWAYS AS (to_tsvector('simple', coalesce(kjv_text,''))) STORED;

ALTER TABLE rag_chunk ADD COLUMN IF NOT EXISTS fts_gr tsvector
  GENERATED ALWAYS AS (
    to_tsvector('simple', coalesce(greek_stripped,'') || ' ' || coalesce(lexeme_text,''))
  ) STORED;

CREATE INDEX IF NOT EXISTS rag_chunk_embedding_hnsw ON rag_chunk
  USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
CREATE INDEX IF NOT EXISTS rag_chunk_fts_id_gin ON rag_chunk USING gin (fts_id);
CREATE INDEX IF NOT EXISTS rag_chunk_fts_en_gin ON rag_chunk USING gin (fts_en);
CREATE INDEX IF NOT EXISTS rag_chunk_fts_gr_gin ON rag_chunk USING gin (fts_gr);
CREATE INDEX IF NOT EXISTS rag_chunk_greek_trgm ON rag_chunk
  USING gin (greek_stripped gin_trgm_ops);

-- trigger dirty flag
CREATE OR REPLACE FUNCTION rag_mark_dirty() RETURNS trigger AS $$
BEGIN NEW.dirty := true; NEW.state := 'chunked'; RETURN NEW; END $$ LANGUAGE plpgsql;
```

**Mengapa `GENERATED`, bukan trigger?** Bentuk dua-argumen `to_tsvector('simple', …)` bersifat *immutable*, sehingga sah dijadikan generated column. Lebih murah dan tidak bisa lupa (uji: berhasil di PG 16, kata Yunani ikut terindeks).

**Urutan hook:** `_auto_init()` milik ORM harus selesai dulu (tabel + kolom biasa), baru DDL di atas dijalankan. Implementasinya:

```python
def _auto_init(self):
    res = super()._auto_init()
    if self._table == 'rag_chunk':
        self.env.cr.execute(SQL_DDL)   # idempoten: IF NOT EXISTS
    return res
```

---

## 11. Hak akses

| Grup | Hak |
|---|---|
| **RAG User** | baca `rag_verse`, `rag_pericope`, `rag_variant`; buat `rag_query_log`/`rag_query_hit`; baca log **miliknya sendiri** |
| **RAG Manager** | semua di atas + CRUD `rag_config`, `rag_verse`, `rag_chunk`, `rag_variant`, `rag_import_batch`; re-embed; lihat semua log |

Record rule pada `rag_query_log`:

```xml
<rule id="rule_query_log_own" model_id="model_rag_query_log">
  <domain>[('user_id','=',user.id)]</domain>
  <groups><group ref="group_rag_user"/></groups>
</rule>
```

---

## 12. Yang sengaja **tidak** dibuat sekarang

| Tidak dibuat | Alasan | Kapan ditambahkan |
|---|---|---|
| Tabel leksikon (`rag_lexicon_entry`) | Strong's + parsing sudah cukup; Abbott-Smith/Thayer menyusul | setelah MVP, tanpa ubah skema inti |
| Tabel tema teologis (`rag_theme`) | belum ada dataset | Fase 5 bila diperlukan |
| Embedding tingkat perikop | 39 ayat belum butuh | tambah **baris** `rag_chunk`, bukan tabel |
| Multi-kitab | lingkup hanya Roma 8 | `rag_book` sudah siap menampung |
| `halfvec`/`sparsevec` | `pgvector` 0.6.0 belum mendukung | jika upgrade ke 0.8.x |

---

## 12b. Tambahan saat implementasi: ekspansi kueri

Pertanyaan generik ("keselamatan") tidak selalu menemukan ayat yang relevan secara semantik — Roma 8:29–30 hanya peringkat 20 dari 39. Ditambahkan dua tabel:

| Tabel | Isi |
|---|---|
| `rag_query_expansion` | `term` (istilah pertanyaan), `sequence`, `active`, `note` |
| `rag_query_expansion_line` | `expansion_id`, `word` (padanan yang ikut dicari) |

Padanan ditambahkan ke tsquery full-text (bukan ke vektor), dan yang dipakai dicatat di `stage_ms['expanded']` untuk audit. 12 istilah awal disediakan lewat data `noupdate`.

**Dampak terukur:** full-text yang semula 0 hasil menjadi 5 chunk; Roma 8:29 naik dari dense-20 ke **RRF-3**.

---

## 13. Ringkasan angka

| Metrik | Nilai |
|---|---|
| Tabel | **17 inti** (4 master enumerasi + 11 inti + 2 ekspansi kueri) + 3 tabel wizard sementara |
| Collection pencarian | **1** (`rag_chunk`) |
| Dimensi vektor | 1024 |
| Ukuran vektor/baris | 4.100 byte |
| Estimasi total data 39 ayat | < 1 MB |
| Indeks vektor | HNSW, m=16, ef_construction=64 |
| Indeks teks | 3× GIN tsvector + 1× GIN trigram |
| Kolom di luar ORM | 1 `vector` + 3 `tsvector` (generated) |
| Tabel wizard (sementara) | `rag_import_wizard`, `rag_chunking_wizard`, `rag_query_wizard` (+1 tabel relasi) |

### Field yang ditambahkan saat implementasi

| Model | Field | Alasan |
|---|---|---|
| `rag.embedding.model` | `api_model` | nilai `model` untuk API harus sama dengan `--alias` llama-server (`bge-m3`), bukan nama internal |
| `rag.config` | `sequence` | preset mana yang jadi default (urutan terkecil) |
| `rag.query.log` | `latency_s`, `greek_quotes`, `cited_verse_ids` | tampilan latensi yang tidak menyesatkan, dan tab teks asli |
| `rag.chunk` | `label` (bukan `display_name`) | `display_name` adalah field khusus Odoo |
| `rag.verse` | `content_hash` jadi **computed stored** | hash lama tidak ikut berubah saat teks diedit |
