from odoo import fields, models


class RagQueryExpansion(models.Model):
    _name = 'rag.query.expansion'
    _table = 'rag_query_expansion'
    _description = 'Ekspansi Kueri (sinonim teologis)'
    _order = 'sequence, term'
    _rec_name = 'term'

    term = fields.Char(string='Istilah', required=True, index=True,
                       help='Kata yang muncul pada pertanyaan, mis. "keselamatan".')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    note = fields.Char(string='Catatan')
    line_ids = fields.One2many('rag.query.expansion.line', 'expansion_id', string='Padanan')

    _term_uniq = models.Constraint('unique(term)', 'Istilah ekspansi harus unik.')


class RagQueryExpansionLine(models.Model):
    _name = 'rag.query.expansion.line'
    _table = 'rag_query_expansion_line'
    _description = 'Padanan Istilah Ekspansi'
    _order = 'expansion_id, id'

    expansion_id = fields.Many2one('rag.query.expansion', required=True, ondelete='cascade', index=True)
    word = fields.Char(string='Padanan', required=True,
                       help='Kata/frasa yang ditambahkan ke pencarian full-text.')
