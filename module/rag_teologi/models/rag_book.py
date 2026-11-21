from odoo import fields, models


class RagBook(models.Model):
    _name = 'rag.book'
    _table = 'rag_book'
    _description = 'Kitab'
    _order = 'sequence, id'

    code = fields.Char(string='Kode', required=True, help='Contoh: ROM')
    name_id = fields.Char(string='Nama (ID)', required=True)
    name_en = fields.Char(string='Nama (EN)')
    name_gr = fields.Char(string='Nama (Yunani)')
    chapter_count = fields.Integer(string='Jumlah Pasal')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    pericope_ids = fields.One2many('rag.pericope', 'book_id', string='Perikop')
    verse_ids = fields.One2many('rag.verse', 'book_id', string='Ayat')

    _code_uniq = models.Constraint('unique(code)', 'Kode kitab harus unik.')
