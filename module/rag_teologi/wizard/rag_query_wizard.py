from odoo import api, fields, models


class RagQueryWizard(models.TransientModel):
    _name = 'rag.query.wizard'
    _description = 'Konsol Tanya RAG'
    _rec_name = 'name'

    name = fields.Char(string='Judul', default='Tanya RAG', readonly=True)

    question = fields.Text(string='Pertanyaan', required=True)
    config_id = fields.Many2one(
        'rag.config', string='Pengaturan RAG',
        default=lambda self: self.env['rag.config'].get_active())
    prompt_template_id = fields.Many2one(
        'rag.prompt.template', string='Templat Prompt',
        compute='_compute_prompt_template', store=True, readonly=False,
        help='Templat bawaan diambil dari Pengaturan RAG; boleh diganti per kueri.')
    answer = fields.Text(string='Jawaban', readonly=True)
    info = fields.Char(string='Info', readonly=True)
    log_id = fields.Many2one('rag.query.log', string='Riwayat', readonly=True)
    greek_quotes = fields.Text(string='Teks Asli (Yunani)',
                               related='log_id.greek_quotes', readonly=True)
    hit_ids = fields.Many2many('rag.chunk', string='Ayat Terambil', readonly=True)

    @api.depends('config_id')
    def _compute_prompt_template(self):
        for rec in self:
            rec.prompt_template_id = rec.config_id.prompt_template_id

    def action_ask(self):
        self.ensure_one()
        log = self.env['rag.query.service'].ask(
            self.question, self.config_id or None, self.prompt_template_id or None)
        self.write({
            'log_id': log.id,
            'answer': log.answer,
            'info': "%s · %s · %d ms · %d ayat · %s" % (
                log.config_id.name or '-', log.route_id.name or '-',
                log.latency_ms or 0, log.hit_count, log.state),
            'hit_ids': [(6, 0, log.hit_ids.mapped('chunk_id').ids)],
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'rag.query.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
