import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

from ..hooks import ensure_chunk_schema
from .embedding_client import EmbeddingError, embed_texts

_logger = logging.getLogger(__name__)

MAX_RETRY = 3      # setelah ini chunk ditandai error dan tidak dicoba cron
BATCH_SIZE = 16    # jumlah teks per permintaan HTTP


class RagChunk(models.Model):
    _name = 'rag.chunk'
    _table = 'rag_chunk'
    _description = 'Chunk (collection pencarian: vektor + full-text)'
    _order = 'verse_id, chunk_kind_id'
    _rec_name = 'label'

    verse_id = fields.Many2one('rag.verse', string='Ayat', required=True, ondelete='cascade', index=True)
    pericope_id = fields.Many2one('rag.pericope', string='Perikop', ondelete='set null', index=True)
    chunk_kind_id = fields.Many2one('rag.chunk.kind', string='Jenis Unit', required=True, ondelete='restrict', index=True)
    embedding_model_id = fields.Many2one('rag.embedding.model', string='Model Embedding', ondelete='restrict')
    seq = fields.Integer(string='Urutan', default=10)
    label = fields.Char(string='Label', compute='_compute_label', store=True)

    lai_text = fields.Text(string='Teks Indonesia')
    kjv_text = fields.Text(string='Teks Inggris')
    greek_stripped = fields.Text(string='Yunani tanpa aksen')
    lexeme_text = fields.Text(string="Lema & Strong's", help='Kata dasar + nomor Strong, menambah daya cari full-text.')

    embed_text = fields.Text(string='Teks untuk Embedding', help='Komposisi deterministik yang di-embed.')
    embed_hash = fields.Char(string='Hash Embedding', size=64)
    token_est = fields.Integer(string='Perkiraan Token')

    state = fields.Selection(
        [('draft', 'Draf'), ('chunked', 'Siap Embed'), ('embedded', 'Ter-embed'), ('error', 'Galat')],
        string='Status', default='chunked', required=True, index=True,
    )
    dirty = fields.Boolean(string='Perlu Diproses', default=True, index=True)
    retry_count = fields.Integer(string='Percobaan', default=0)
    last_error = fields.Text(string='Galat Terakhir')
    embedded_at = fields.Datetime(string='Di-embed Pada')
    active = fields.Boolean(default=True)

    _verse_kind_uniq = models.Constraint(
        'unique(verse_id, chunk_kind_id)',
        'Chunk ayat+jenis ini sudah ada.')

    def _auto_init(self):
        """ORM membuat tabel lebih dulu, lalu kolom vector/tsvector ditambahkan."""
        res = super()._auto_init()
        ensure_chunk_schema(self.env.cr)
        return res

    @api.depends('verse_id', 'chunk_kind_id')
    def _compute_label(self):
        for rec in self:
            rec.label = "%s [%s]" % (
                rec.verse_id.ref_label or '',
                rec.chunk_kind_id.code or '',
            )

    # ------------------------------------------------------------- embedding
    def _konfigurasi(self):
        cfg = self.env['rag.config'].get_active()
        if not cfg:
            raise UserError("Belum ada konfigurasi RAG yang aktif.")
        model = cfg.embedding_model_id
        if not model:
            raise UserError("Konfigurasi RAG belum menunjuk model embedding.")
        endpoint = model.endpoint or (cfg.embed_base_url.rstrip('/') + '/embeddings')
        return cfg, model, endpoint

    def _tulis_vektor(self, model, vectors):
        """Simpan vektor lewat SQL karena kolomnya tidak dikenal ORM."""
        for chunk, vec in zip(self, vectors):
            if len(vec) != model.dimensions:
                raise EmbeddingError(
                    "Dimensi vektor %d tidak sesuai konfigurasi (%d)."
                    % (len(vec), model.dimensions)
                )
            literal = '[' + ','.join('%.7g' % float(x) for x in vec) + ']'
            self.env.cr.execute(
                """
                UPDATE rag_chunk
                   SET embedding = %s::vector,
                       state = 'embedded',
                       dirty = false,
                       retry_count = 0,
                       last_error = NULL,
                       embedding_model_id = %s,
                       embedded_at = now()
                 WHERE id = %s
                """,
                (literal, model.id, chunk.id),
            )

    def _tandai_gagal(self, pesan):
        for chunk in self:
            chunk.write({
                'retry_count': chunk.retry_count + 1,
                'last_error': pesan[:2000],
                'state': 'error' if chunk.retry_count + 1 >= MAX_RETRY else 'chunked',
            })

    def _segarkan_ayat(self):
        """Ayat menjadi 'embedded' bila seluruh chunk-nya sudah ter-embed."""
        for verse in self.mapped('verse_id'):
            semua = verse.chunk_ids
            if semua and all(c.state == 'embedded' for c in semua):
                verse.write({'state': 'embedded', 'dirty': False})

    def _embed(self):
        """Embed recordset ini; kembalikan statistik."""
        stat = {'diminta': len(self), 'berhasil': 0, 'gagal': 0, 'galat': []}
        if not self:
            return stat
        # Odoo 18 menunda write() ORM sampai flush. Tanpa ini, write(state=...)
        # bisa dieksekusi SETELAH UPDATE vektor di bawah dan menimpanya.
        self.env.flush_all()
        cfg, model, endpoint = self._konfigurasi()
        teks = [c.embed_text or '' for c in self]

        for awal in range(0, len(self), BATCH_SIZE):
            potong = self[awal:awal + BATCH_SIZE]
            masukan = teks[awal:awal + BATCH_SIZE]
            if any(not t.strip() for t in masukan):
                potong._tandai_gagal("embed_text kosong")
                stat['gagal'] += len(potong)
                stat['galat'].append("Batch %d: embed_text kosong" % (awal // BATCH_SIZE + 1))
                continue
            try:
                vectors = embed_texts(
                    endpoint=endpoint,
                    api_model=model.api_model or model.name,
                    texts=masukan,
                    timeout=cfg.timeout_embed_s or 30,
                )
                potong._tulis_vektor(model, vectors)
                stat['berhasil'] += len(potong)
            except EmbeddingError as exc:
                potong._tandai_gagal(str(exc))
                stat['gagal'] += len(potong)
                stat['galat'].append(str(exc))
                _logger.warning("Embedding batch %d gagal: %s", awal // BATCH_SIZE + 1, exc)
            except Exception as exc:  # noqa: BLE001
                potong._tandai_gagal("%s: %s" % (type(exc).__name__, exc))
                stat['gagal'] += len(potong)
                stat['galat'].append(str(exc))
                _logger.exception("Embedding batch %d error tak terduga", awal // BATCH_SIZE + 1)

        self.invalidate_recordset()
        self._segarkan_ayat()
        return stat

    # -------------------------------------------------------------- antrean
    @api.model
    def _cron_embed(self, limit=64):
        """Dipanggil ir.cron: proses chunk yang menunggu embedding."""
        chunks = self.search([
            ('embed_text', '!=', False),
            ('retry_count', '<', MAX_RETRY),
            '|',
            ('state', 'in', ('chunked', 'error')),
            ('dirty', '=', True),
        ], limit=limit, order='id')
        if not chunks:
            return {'diminta': 0, 'berhasil': 0, 'gagal': 0, 'galat': []}
        stat = chunks._embed()
        self.env.cr.commit()
        _logger.info(
            "RAG embedding: %(berhasil)d berhasil, %(gagal)d gagal dari %(diminta)d",
            stat)
        return stat

    # ---------------------------------------------------------------- aksi
    def action_reembed(self):
        """Tombol manual untuk RAG Manager."""
        self.write({'state': 'chunked', 'dirty': True, 'retry_count': 0, 'last_error': False})
        stat = self._embed()
        self.env.cr.commit()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Re-embed selesai',
                'message': '%(berhasil)d berhasil, %(gagal)d gagal.' % stat,
                'type': 'success' if not stat['gagal'] else 'warning',
                'sticky': False,
            },
        }

    def action_lihat_galat(self):
        for chunk in self:
            if chunk.last_error:
                raise UserError("RAG %s:\n\n%s" % (chunk.label, chunk.last_error))
        raise UserError("Tidak ada galat tercatat pada chunk terpilih.")
