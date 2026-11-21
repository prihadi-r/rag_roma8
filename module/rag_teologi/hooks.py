"""SQL hook: kolom dan indeks yang tidak bisa dikelola ORM Odoo.

Kolom `vector` (pgvector) dan `tsvector` tidak dikenal Odoo, sehingga tidak
dideklarasikan sebagai field. Semuanya dibuat di sini secara idempoten
(`IF NOT EXISTS`) agar aman dijalankan berulang pada install maupun upgrade.
"""
import logging

from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

#: Dimensi embedding terkunci pada bge-m3.
EMBEDDING_DIM = 1024


def _table_exists(cr, table):
    cr.execute("SELECT 1 FROM information_schema.tables WHERE table_name = %s", (table,))
    return bool(cr.fetchone())


def _column_exists(cr, table, column):
    cr.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = %s AND column_name = %s",
        (table, column),
    )
    return bool(cr.fetchone())


def _index_exists(cr, name):
    cr.execute("SELECT 1 FROM pg_class WHERE relname = %s AND relkind = 'i'", (name,))
    return bool(cr.fetchone())


def _extension_version(cr, name):
    cr.execute(
        "SELECT extversion FROM pg_extension WHERE extname = %s", (name,)
    )
    row = cr.fetchone()
    return row[0] if row else None


def ensure_chunk_schema(cr):
    """Tambahkan kolom vektor/tsvector dan seluruh indeks pada rag_chunk."""
    if not _table_exists(cr, 'rag_chunk'):
        return

    if not _extension_version(cr, 'vector'):
        raise UserError(
            "Ekstensi pgvector ('vector') belum ada di database ini.\n\n"
            "Jalankan sebagai superuser PostgreSQL:\n"
            "    CREATE EXTENSION vector;\n"
            "    CREATE EXTENSION pg_trgm;\n\n"
            "Ekstensi tidak 'trusted', sehingga user Odoo tidak dapat "
            "membuatnya sendiri."
        )

    # ---- kolom di luar ORM -------------------------------------------------
    # Diperiksa lebih dulu: ALTER TABLE ... IF NOT EXISTS tetap mengambil
    # ACCESS EXCLUSIVE lock, dan itu pernah membuat registry gagal dimuat
    # (lock timeout) ketika layanan Odoo sedang melayani permintaan.
    if not _column_exists(cr, 'rag_chunk', 'embedding'):
        cr.execute(
            f"ALTER TABLE rag_chunk ADD COLUMN embedding vector({EMBEDDING_DIM})"
        )
    if not _column_exists(cr, 'rag_chunk', 'fts_id'):
        cr.execute(
            "ALTER TABLE rag_chunk ADD COLUMN fts_id tsvector "
            "GENERATED ALWAYS AS (to_tsvector('simple', coalesce(lai_text, ''))) STORED"
        )
    if not _column_exists(cr, 'rag_chunk', 'fts_en'):
        cr.execute(
            "ALTER TABLE rag_chunk ADD COLUMN fts_en tsvector "
            "GENERATED ALWAYS AS (to_tsvector('simple', coalesce(kjv_text, ''))) STORED"
        )
    if not _column_exists(cr, 'rag_chunk', 'fts_gr'):
        cr.execute(
            "ALTER TABLE rag_chunk ADD COLUMN fts_gr tsvector "
            "GENERATED ALWAYS AS (to_tsvector('simple', "
            "coalesce(greek_stripped, '') || ' ' || coalesce(lexeme_text, ''))) STORED"
        )

    # ---- indeks ------------------------------------------------------------
    indeks = [
        ("rag_chunk_embedding_hnsw",
         "CREATE INDEX rag_chunk_embedding_hnsw ON rag_chunk "
         "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)"),
        ("rag_chunk_fts_id_gin",
         "CREATE INDEX rag_chunk_fts_id_gin ON rag_chunk USING gin (fts_id)"),
        ("rag_chunk_fts_en_gin",
         "CREATE INDEX rag_chunk_fts_en_gin ON rag_chunk USING gin (fts_en)"),
        ("rag_chunk_fts_gr_gin",
         "CREATE INDEX rag_chunk_fts_gr_gin ON rag_chunk USING gin (fts_gr)"),
        ("rag_chunk_greek_trgm",
         "CREATE INDEX rag_chunk_greek_trgm ON rag_chunk "
         "USING gin (greek_stripped gin_trgm_ops)"),
        ("rag_chunk_dirty_idx",
         "CREATE INDEX rag_chunk_dirty_idx ON rag_chunk (dirty) WHERE dirty"),
    ]
    for nama, ddl in indeks:
        if not _index_exists(cr, nama):
            cr.execute(ddl)

    # ---- indeks parsial pada tabel lain ------------------------------------
    # Tabel-tabel ini bisa belum ada saat _auto_init() rag_chunk berjalan
    # (urutan pembuatan tabel mengikuti urutan model). post_init_hook akan
    # memanggil fungsi ini sekali lagi setelah seluruh tabel selesai dibuat.
    if _table_exists(cr, 'rag_verse') and not _index_exists(cr, 'rag_verse_dirty_idx'):
        cr.execute("CREATE INDEX rag_verse_dirty_idx ON rag_verse (dirty) WHERE dirty")
    if _table_exists(cr, 'rag_config') and _index_exists(cr, 'rag_config_active_uniq'):
        # Beberapa konfigurasi kini boleh aktif sekaligus (preset yang bisa
        # dipilih per kueri). Indeks unik lama dihapus.
        cr.execute("DROP INDEX IF EXISTS rag_config_active_uniq")

    _logger.info("RAG Teologi: skema rag_chunk (vector/tsvector) siap.")


def post_init_hook(env):
    """Dipanggil Odoo setelah modul terpasang."""
    ensure_chunk_schema(env.cr)
