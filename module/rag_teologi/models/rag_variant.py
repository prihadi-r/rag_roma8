from odoo import fields, models


class RagVariant(models.Model):
    _name = 'rag.variant'
    _table = 'rag_variant'
    _description = 'Varian Tekstual (data apparatus, bukan inferensi LLM)'
    _order = 'verse_id, seq'

    verse_id = fields.Many2one('rag.verse', string='Ayat', required=True, ondelete='cascade', index=True)
    seq = fields.Integer(string='Urutan', default=1)
    clause_ref = fields.Char(string='Klausa', help='Contoh: 8:1b')
    witness_id = fields.Many2one('rag.witness', string='Saksi', required=True, ondelete='restrict')
    variant_type_id = fields.Many2one('rag.variant.type', string='Jenis Varian', required=True, ondelete='restrict')
    byz_text = fields.Text(string='Bacaan Byzantine')
    other_text = fields.Text(string='Bacaan Saksi Lain')
    apparatus_note = fields.Text(string='Notasi Apparatus', help='Notasi asli Robinson-Pierpont, disimpan apa adanya.')
    is_significant = fields.Boolean(string='Penting', default=True)
    source = fields.Char(string='Sumber', default='RP2018 apparatus')

    _variant_seq_uniq = models.Constraint('unique(verse_id, seq)', 'Urutan varian harus unik per ayat.')
