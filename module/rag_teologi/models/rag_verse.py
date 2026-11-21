import hashlib

from odoo import api, fields, models
from odoo.exceptions import UserError


class RagVerse(models.Model):
    _name = 'rag.verse'
    _table = 'rag_verse'
    _description = 'Ayat (child — sumber kebenaran teks)'
    _order = 'chapter, verse_no'
    _rec_name = 'ref_label'

    book_id = fields.Many2one('rag.book', string='Kitab', required=True, ondelete='restrict', index=True)
    pericope_id = fields.Many2one('rag.pericope', string='Perikop', ondelete='set null', index=True)
    chapter = fields.Integer(string='Pasal', required=True)
    verse_no = fields.Integer(string='Ayat', required=True)
    ref_label = fields.Char(string='Referensi', compute='_compute_ref_label', store=True)

    paragraph_start = fields.Boolean(string='Awal Paragraf', help='Penanda pilcrow (¶) pada edisi Robinson-Pierpont.')

    greek_accented = fields.Text(string='Yunani (berdiakritik)')
    greek_stripped = fields.Text(string='Yunani (tanpa aksen)')
    transliteration = fields.Char(string='Transliterasi')
    words = fields.Json(string='Kata & Morfologi', help='Daftar {surface, strongs, morph, alt}.')
    word_count = fields.Integer(string='Jumlah Kata', compute='_compute_word_count', store=True)

    kjv = fields.Text(string='KJV (bersih)')
    kjv_raw = fields.Text(string='KJV (asli)', help='Menyimpan kurung siku kata sisipan penerjemah.')
    ind = fields.Text(string='Indonesia')
    ind_source = fields.Char(string='Sumber Indonesia', default='AYT')

    variant_ids = fields.One2many('rag.variant', 'verse_id', string='Varian')
    variant_count = fields.Integer(string='Jumlah Varian', compute='_compute_variant_count', store=True)

    state = fields.Selection(
        [('draft', 'Draf'), ('chunked', 'Ter-chunk'), ('embedded', 'Ter-embed'), ('error', 'Galat')],
        string='Status', default='draft', required=True, index=True,
    )
    dirty = fields.Boolean(string='Perlu Diproses', default=True)
    content_hash = fields.Char(string='Hash Konten', size=64, index=True,
                               compute='_compute_content_hash', store=True,
                               help='Dihitung ulang otomatis saat teks berubah.')
    source_note = fields.Text(string='Catatan Sumber')
    active = fields.Boolean(default=True)

    chunk_ids = fields.One2many('rag.chunk', 'verse_id', string='Chunk')

    _ref_uniq = models.Constraint('unique(book_id, chapter, verse_no)', 'Ayat ini sudah ada.')

    _verse_positive = models.Constraint('check(verse_no > 0)', 'Nomor ayat harus positif.')

    @api.depends('book_id.name_id', 'chapter', 'verse_no')
    def _compute_ref_label(self):
        for rec in self:
            rec.ref_label = f"{rec.book_id.name_id or ''} {rec.chapter}:{rec.verse_no}".strip()

    @api.depends('greek_accented', 'greek_stripped', 'kjv', 'ind')
    def _compute_content_hash(self):
        for rec in self:
            bahan = "|".join([rec.greek_accented or '', rec.greek_stripped or '',
                              rec.kjv or '', rec.ind or ''])
            rec.content_hash = hashlib.sha256(bahan.encode('utf-8')).hexdigest()

    @api.depends('words')
    def _compute_word_count(self):
        for rec in self:
            rec.word_count = len(rec.words or [])

    @api.depends('variant_ids')
    def _compute_variant_count(self):
        for rec in self:
            rec.variant_count = len(rec.variant_ids)

    def action_reembed_chunks(self):
        """Tombol manual pada form ayat (RAG Manager)."""
        chunks = self.mapped('chunk_ids')
        if not chunks:
            raise UserError("Ayat ini belum memiliki chunk. Jalankan Chunking lebih dulu.")
        return chunks.action_reembed()

    def write(self, vals):
        """Setiap perubahan teks/morfologi menandai ayat DAN chunk-nya kotor."""
        pemicu = {'greek_accented', 'greek_stripped', 'kjv', 'kjv_raw', 'ind', 'words', 'transliteration'}
        berubah = bool(pemicu & set(vals))
        if berubah:
            vals.setdefault('dirty', True)
            # ayat yang sudah ter-embed harus turun status agar cron memprosesnya lagi
            if any(rec.state == 'embedded' for rec in self):
                vals.setdefault('state', 'chunked')
        res = super().write(vals)
        if berubah:
            chunks = self.mapped('chunk_ids')
            if chunks:
                chunks.write({'dirty': True, 'state': 'chunked'})
        return res
