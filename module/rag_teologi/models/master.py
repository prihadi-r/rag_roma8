from odoo import fields, models


class RagChunkKind(models.Model):
    _name = 'rag.chunk.kind'
    _table = 'rag_chunk_kind'
    _description = 'Jenis Unit Pencarian'
    _order = 'sequence, id'

    name = fields.Char(string='Nama', required=True, translate=True)
    code = fields.Char(string='Kode', required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint('unique(code)', 'Kode jenis unit harus unik.')


class RagWitness(models.Model):
    _name = 'rag.witness'
    _table = 'rag_witness'
    _description = 'Saksi Tekstual'
    _order = 'sequence, id'

    name = fields.Char(string='Nama', required=True)
    code = fields.Char(string='Kode', required=True)
    description = fields.Text(string='Keterangan')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint('unique(code)', 'Kode saksi harus unik.')


class RagVariantType(models.Model):
    _name = 'rag.variant.type'
    _table = 'rag_variant_type'
    _description = 'Jenis Varian Tekstual'
    _order = 'sequence, id'

    name = fields.Char(string='Nama', required=True, translate=True)
    code = fields.Char(string='Kode', required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint('unique(code)', 'Kode jenis varian harus unik.')


class RagQueryRoute(models.Model):
    _name = 'rag.query.route'
    _table = 'rag_query_route'
    _description = 'Jalur Kueri'
    _order = 'sequence, id'

    name = fields.Char(string='Nama', required=True, translate=True)
    code = fields.Char(string='Kode', required=True)
    description = fields.Text(string='Keterangan')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint('unique(code)', 'Kode jalur kueri harus unik.')
