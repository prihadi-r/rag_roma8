from odoo import api, fields, models


class RagPericope(models.Model):
    _name = 'rag.pericope'
    _table = 'rag_pericope'
    _description = 'Perikop (parent — unit konteks)'
    _order = 'chapter, verse_start'

    book_id = fields.Many2one('rag.book', string='Kitab', required=True, ondelete='cascade', index=True)
    chapter = fields.Integer(string='Pasal', required=True)
    verse_start = fields.Integer(string='Ayat Awal', required=True)
    verse_end = fields.Integer(string='Ayat Akhir', required=True)
    title_id = fields.Char(string='Judul (ID)', required=True)
    title_en = fields.Char(string='Judul (EN)')
    summary_id = fields.Text(string='Ringkasan (ID)', help='Dipakai sebagai konteks parent saat membangun prompt.')
    sequence = fields.Integer(default=10)
    state = fields.Selection(
        [('draft', 'Draf'), ('ready', 'Siap'), ('error', 'Galat')],
        string='Status', default='draft', required=True,
    )
    active = fields.Boolean(default=True)

    verse_ids = fields.One2many('rag.verse', 'pericope_id', string='Ayat')
    verse_count = fields.Integer(string='Jumlah Ayat', compute='_compute_verse_count', store=True)
    name = fields.Char(string='Label', compute='_compute_name', store=True)

    _range_uniq = models.Constraint(
        'unique(book_id, chapter, verse_start, verse_end)',
        'Rentang perikop ini sudah ada.')
    _range_valid = models.Constraint(
        'check(verse_end >= verse_start)',
        'Ayat akhir harus >= ayat awal.')

    @api.depends('verse_ids')
    def _compute_verse_count(self):
        for rec in self:
            rec.verse_count = len(rec.verse_ids)

    @api.depends('book_id.name_id', 'chapter', 'verse_start', 'verse_end', 'title_id')
    def _compute_name(self):
        for rec in self:
            kitab = rec.book_id.name_id or ''
            rec.name = f"{kitab} {rec.chapter}:{rec.verse_start}–{rec.verse_end} — {rec.title_id or ''}".strip()
