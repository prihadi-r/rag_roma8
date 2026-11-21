import re

from odoo import api, fields, models
from odoo.exceptions import UserError


class RagQueryLog(models.Model):
    _name = 'rag.query.log'
    _table = 'rag_query_log'
    _description = 'Riwayat Kueri RAG'
    _order = 'create_date desc'

    name = fields.Char(string='Kueri', compute='_compute_name', store=True)
    question = fields.Text(string='Pertanyaan', required=True)
    route_id = fields.Many2one('rag.query.route', string='Jalur', ondelete='restrict', index=True)
    config_id = fields.Many2one('rag.config', string='Konfigurasi', ondelete='set null')

    params = fields.Json(string='Parameter', help='top_k, rrf_k, temperature saat kueri dijalankan.')
    answer = fields.Text(string='Jawaban')
    citations = fields.Json(string='Sitasi')

    latency_ms = fields.Integer(string='Latensi (ms)')
    latency_s = fields.Char(string='Latensi', compute='_compute_latency_s')
    stage_ms = fields.Json(string='Latensi per Tahap', help='{embed, search, context, generate}')
    prompt_tokens = fields.Integer(string='Token Prompt')
    completion_tokens = fields.Integer(string='Token Jawaban')

    state = fields.Selection(
        [('draft', 'Draf'), ('running', 'Berjalan'),
         ('success', 'Berhasil'), ('error', 'Galat')],
        string='Status', default='draft', required=True, index=True,
    )
    error = fields.Text(string='Galat')
    user_id = fields.Many2one('res.users', string='Pengguna', default=lambda self: self.env.user, index=True)

    hit_ids = fields.One2many('rag.query.hit', 'query_id', string='Ayat Terambil')
    hit_count = fields.Integer(string='Jumlah Hit', compute='_compute_hit_count', store=True)

    # --- teks asli ayat yang dikutip (ditampilkan sebagai tab di form)
    cited_verse_ids = fields.Many2many('rag.verse', string='Ayat Dikutip',
                                       compute='_compute_greek_quotes')
    greek_quotes = fields.Text(string='Teks Asli (Yunani)',
                               compute='_compute_greek_quotes')

    #: "Roma 8:29", "8:29–30", "Rm 8:1"
    _POLA_KUTIPAN = re.compile(
        r'\b(?:roma|rom|rm)?\s*8\s*[:.]\s*(\d{1,2})(?:\s*[-–]\s*(\d{1,2}))?',
        re.IGNORECASE,
    )

    # ------------------------------------------------------------------ compute
    @api.depends('latency_ms')
    def _compute_latency_s(self):
        for rec in self:
            rec.latency_s = ('%.1f s' % (rec.latency_ms / 1000.0)) if rec.latency_ms else '-'

    @api.depends('question')
    def _compute_name(self):
        for rec in self:
            rec.name = (rec.question or '')[:60]

    @api.depends('hit_ids')
    def _compute_hit_count(self):
        for rec in self:
            rec.hit_count = len(rec.hit_ids)

    def _nomor_dikutip(self):
        """Nomor ayat yang disebut di jawaban, mis. 8:29 atau 8:29–30."""
        nomor = set()
        for m in self._POLA_KUTIPAN.finditer(self.answer or ''):
            awal = int(m.group(1))
            akhir = int(m.group(2)) if m.group(2) else awal
            if akhir < awal or akhir - awal > 10:
                akhir = awal
            nomor.update(range(awal, akhir + 1))
        return sorted(n for n in nomor if 1 <= n <= 39)

    @api.depends('hit_ids', 'answer')
    def _compute_greek_quotes(self):
        """Bahasa asli untuk ayat yang DIKUTIP jawaban; bila belum ada, ayat terambil.

        Ayat yang dikutip bisa saja tidak termasuk hasil pencarian (mis. 8:30
        yang masuk lewat perluasan perikop), jadi daftarnya diambil dari jawaban
        lebih dulu, bukan hanya dari `hit_ids`.
        """
        for rec in self:
            terambil = {h.chunk_id.verse_id.id for h in rec.hit_ids if h.injected}
            nomor = rec._nomor_dikutip()

            if nomor:
                verses = rec.env['rag.verse'].search(
                    [('chapter', '=', 8), ('verse_no', 'in', nomor)], order='verse_no')
                keterangan = "[Teks asli untuk ayat yang dikutip dalam jawaban]"
            else:
                verses = rec.env['rag.verse']
                lihat = set()
                for h in rec.hit_ids:
                    v = h.chunk_id.verse_id
                    if h.injected and v.id not in lihat:
                        lihat.add(v.id)
                        verses |= v
                keterangan = "[Jawaban belum menyebut ayat; ini ayat yang terambil]"

            blok = [keterangan, ""]
            for verse in verses:
                asal = "hasil pencarian" if verse.id in terambil else "konteks perikop"
                blok.append("[%s]  (%s)" % (verse.ref_label, asal))
                blok.append("Yunani     : %s" % (verse.greek_accented or '-'))
                if verse.transliteration:
                    blok.append("Translit   : %s" % verse.transliteration)
                if verse.greek_stripped:
                    blok.append("Tanpa aksen: %s" % verse.greek_stripped)
                blok.append("")

            rec.cited_verse_ids = verses
            rec.greek_quotes = "\n".join(blok).strip()

    # ------------------------------------------------------------------ aksi
    def action_run(self):
        """Eksekusi kueri dari record ini (tombol pada form & list)."""
        self.ensure_one()
        if not (self.question or '').strip():
            raise UserError("Isi pertanyaan terlebih dahulu.")
        self.env['rag.query.service']._jalankan(self)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'rag.query.log',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }


class RagQueryHit(models.Model):
    _name = 'rag.query.hit'
    _table = 'rag_query_hit'
    _description = 'Ayat Terambil per Kueri (dasar evaluasi)'
    _order = 'query_id, position'

    query_id = fields.Many2one('rag.query.log', string='Kueri', required=True, ondelete='cascade', index=True)
    chunk_id = fields.Many2one('rag.chunk', string='Chunk', required=True, ondelete='cascade', index=True)
    rank_dense = fields.Integer(string='Peringkat Vektor')
    rank_fts = fields.Integer(string='Peringkat Full-text')
    score_dense = fields.Float(string='Skor Vektor', digits=(10, 6))
    score_fts = fields.Float(string='Skor Full-text', digits=(10, 6))
    rrf_score = fields.Float(string='Skor RRF', digits=(10, 6))
    position = fields.Integer(string='Posisi Akhir')
    injected = fields.Boolean(string='Masuk Konteks')
