from odoo import api, fields, models


class RagChunkingWizard(models.TransientModel):
    _name = 'rag.chunking.wizard'
    _description = 'Jalankan Chunking'

    hanya_kotor = fields.Boolean(
        string='Hanya yang perlu diproses', default=True,
        help='Batasi pada ayat berstatus draft/error atau bertanda kotor.',
    )
    hasil = fields.Text(string='Hasil', readonly=True)

    def action_run(self):
        self.ensure_one()
        stat = self.env['rag.chunker'].run(hanya_kotor=self.hanya_kotor)
        baris = [
            f"ayat diproses : {stat['ayat']}",
            f"chunk dibuat  : {stat['chunk']}",
            f"gagal         : {stat['gagal']}",
        ]
        if stat['galat']:
            baris.append("")
            baris.append("Galat:")
            baris += ["- " + g for g in stat['galat'][:10]]
        self.hasil = "\n".join(baris)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Chunking selesai',
                'message': f"{stat['chunk']} chunk dibuat, {stat['gagal']} gagal.",
                'type': 'success' if not stat['gagal'] else 'warning',
                'sticky': False,
            },
        }
