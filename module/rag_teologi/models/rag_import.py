from odoo import fields, models


class RagImportBatch(models.Model):
    _name = 'rag.import.batch'
    _table = 'rag_import_batch'
    _description = 'Batch Impor Dataset'
    _order = 'create_date desc'

    name = fields.Char(string='Nama', required=True)
    source = fields.Char(string='Sumber', help='byztxt / ebible / lai-api')
    file_hash = fields.Char(string='Hash Berkas', size=64)
    rows_total = fields.Integer(string='Total Baris')
    rows_ok = fields.Integer(string='Berhasil')
    rows_error = fields.Integer(string='Gagal')
    log = fields.Text(string='Catatan')
    state = fields.Selection(
        [('draft', 'Draf'), ('running', 'Berjalan'), ('done', 'Selesai'), ('error', 'Galat')],
        string='Status', default='draft', required=True,
    )
