"""Wizard impor dataset Roma 8 (ayat, perikop, varian).

Sengaja TIDAK melakukan chunking maupun embedding — itu Fase 6.
Wizard ini hanya mengisi master data teks.
"""
import base64
import json
import logging
import os

from odoo import fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class RagImportWizard(models.TransientModel):
    _name = 'rag.import.wizard'
    _description = 'Impor Dataset Roma 8'

    file_data = fields.Binary(string='Berkas JSON', attachment=False)
    file_name = fields.Char(string='Nama Berkas')
    source_path = fields.Char(
        string='Atau path di server',
        default='/opt/odoo18/rag-data/roma8.json',
        help='Dipakai bila tidak ada berkas yang diunggah.',
    )
    reset_variants = fields.Boolean(
        string='Ganti varian lama', default=True,
        help='Varian pada ayat yang diimpor akan dihapus lalu dibuat ulang.',
    )
    batch_id = fields.Many2one('rag.import.batch', string='Batch', readonly=True)

    # ------------------------------------------------------------------ util
    def _baca_json(self):
        self.ensure_one()
        if self.file_data:
            try:
                return json.loads(base64.b64decode(self.file_data).decode('utf-8'))
            except (ValueError, UnicodeDecodeError) as exc:
                raise UserError(f"Berkas JSON tidak valid: {exc}") from exc
        path = (self.source_path or '').strip()
        if not path or not os.path.exists(path):
            raise UserError(
                "Berkas tidak ditemukan.\n\nUnggah berkas JSON, atau isi path yang "
                "bisa dibaca server, misalnya:\n"
                "/opt/odoo18/rag-data/roma8.json"
            )
        with open(path, encoding='utf-8') as fh:
            return json.load(fh)

    # ----------------------------------------------------------------- aksi
    def action_import(self):
        self.ensure_one()
        data = self._baca_json()
        ayat = data.get('ayat') or []
        if not ayat:
            raise UserError("Dataset kosong: tidak ada kunci 'ayat'.")

        meta = data.get('meta') or {}
        sumber = meta.get('sumber') or {}
        batch = self.env['rag.import.batch'].create({
            'name': 'Impor Roma 8 (%s ayat)' % len(ayat),
            'source': 'dataset-json',
            'rows_total': len(ayat),
            'state': 'running',
        })
        self.batch_id = batch

        Book = self.env['rag.book']
        Pericope = self.env['rag.pericope']
        Verse = self.env['rag.verse']
        Variant = self.env['rag.variant']
        Witness = self.env['rag.witness']
        VType = self.env['rag.variant.type']

        book = Book.search([('code', '=', 'ROM')], limit=1)
        book_vals = {
            'code': 'ROM',
            'name_id': 'Roma',
            'name_en': 'Romans',
            'name_gr': 'Πρὸς Ῥωμαίους',
            'chapter_count': 16,
        }
        if book:
            book.write(book_vals)
        else:
            book = Book.create(book_vals)

        jumlah = {'perikop': 0, 'ayat': 0, 'ayat_baru': 0, 'varian': 0, 'dilewati': 0}
        galat = []
        perikop_cache = {}

        for rec in ayat:
            nomor = rec.get('verse')
            try:
                with self.env.cr.savepoint():
                    per_info = rec.get('pericope') or {}
                    awal, akhir = self._parse_rentang(per_info.get('range') or '', nomor)
                    kunci = (rec['chapter'], awal, akhir)

                    per = perikop_cache.get(kunci)
                    if not per:
                        per = Pericope.search([
                            ('book_id', '=', book.id),
                            ('chapter', '=', rec['chapter']),
                            ('verse_start', '=', awal),
                            ('verse_end', '=', akhir),
                        ], limit=1)
                        per_baru = not per
                        vals_per = {
                            'book_id': book.id,
                            'chapter': rec['chapter'],
                            'verse_start': awal,
                            'verse_end': akhir,
                            'title_id': per_info.get('title_id') or 'Tanpa judul',
                            'title_en': per_info.get('title_en'),
                            'state': 'ready',
                        }
                        if per:
                            per.write(vals_per)
                        else:
                            per = Pericope.create(vals_per)
                        perikop_cache[kunci] = per
                    else:
                        per_baru = False

                    verse = Verse.search([
                        ('book_id', '=', book.id),
                        ('chapter', '=', rec['chapter']),
                        ('verse_no', '=', nomor),
                    ], limit=1)
                    ayat_baru = not verse
                    vals_ayat = {
                        'book_id': book.id,
                        'pericope_id': per.id,
                        'chapter': rec['chapter'],
                        'verse_no': nomor,
                        'greek_accented': rec.get('greek_accented'),
                        'greek_stripped': rec.get('greek_stripped'),
                        'transliteration': rec.get('transliteration'),
                        'words': rec.get('words') or [],
                        'kjv': rec.get('kjv'),
                        'kjv_raw': rec.get('kjv_raw'),
                        'ind': rec.get('ind'),
                        'ind_source': 'AYT',
                        'paragraph_start': rec.get('paragraph_start', False),
                        'source_note': self._catatan_sumber(sumber),
                        # sengaja tetap draft: chunking belum dijalankan
                        'state': 'draft',
                        'dirty': True,
                    }
                    if verse:
                        verse.write(vals_ayat)
                    else:
                        # PENTING: hasil create harus di-assign, kalau tidak
                        # verse.id kosong dan varian akan gagal NOT NULL.
                        verse = Verse.create(vals_ayat)

                    if self.reset_variants:
                        verse.variant_ids.unlink()
                    n_varian = 0
                    for i, va in enumerate(rec.get('variants') or [], start=1):
                        w = Witness.search([('code', '=', va.get('witness') or 'NA')], limit=1)
                        t = VType.search([('code', '=', va.get('type') or 'substitution')], limit=1)
                        if not w or not t:
                            raise UserError(
                                "Saksi '%s' atau jenis varian '%s' belum ada di master data."
                                % (va.get('witness'), va.get('type'))
                            )
                        Variant.create({
                            'verse_id': verse.id,
                            'seq': va.get('seq') or i,
                            'clause_ref': va.get('clause_ref'),
                            'witness_id': w.id,
                            'variant_type_id': t.id,
                            'byz_text': va.get('byz_text'),
                            'other_text': va.get('other_text'),
                            'apparatus_note': va.get('apparatus_note'),
                            'source': 'RP2018 apparatus',
                        })
                        n_varian += 1
            except Exception as exc:  # noqa: BLE001
                # savepoint sudah membatalkan baris ini; cache perikop bisa
                # memuat record yang ikut batal, jadi dibersihkan.
                perikop_cache.clear()
                self.env.invalidate_all()
                jumlah['dilewati'] += 1
                pesan = "8:%s → %s: %s" % (
                    nomor, type(exc).__name__, str(exc).strip().replace("\n", " "))
                galat.append(pesan)
                _logger.warning("Impor Roma 8:%s gagal: %s", nomor, exc)
            else:
                jumlah['ayat'] += 1
                jumlah['perikop'] += 1 if per_baru else 0
                jumlah['ayat_baru'] += 1 if ayat_baru else 0
                jumlah['varian'] += n_varian

        batch.write({
            'rows_ok': jumlah['ayat'],
            'rows_error': jumlah['dilewati'],
            'state': 'error' if jumlah['dilewati'] else 'done',
            'log': self._log_teks(jumlah, sumber, galat),
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Impor selesai',
                'message': '%(ayat)d ayat, %(perikop)d perikop, %(varian)d varian.' % jumlah,
                'type': 'success' if not jumlah['dilewati'] else 'warning',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    # ---------------------------------------------------------------- helper
    @staticmethod
    def _parse_rentang(rentang, ayat_default):
        """'8:1-11' → (1, 11)."""
        try:
            bagian = rentang.split('-')
            awal = int(bagian[0].split(':')[1])
            akhir = int(bagian[1]) if len(bagian) > 1 else awal
            return awal, akhir
        except (IndexError, ValueError):
            return ayat_default, ayat_default

    @staticmethod
    def _catatan_sumber(sumber):
        baris = []
        for kunci in ('yunani', 'inggris', 'indonesia'):
            info = sumber.get(kunci) or {}
            if info.get('edisi'):
                baris.append('%s: %s (%s)' % (kunci, info['edisi'], info.get('lisensi', '?')))
        return '\n'.join(baris)

    @staticmethod
    def _log_teks(jumlah, sumber, galat=None):
        rincian = json.dumps(sumber, indent=2, ensure_ascii=False) if sumber else '-'
        teks = (
            "perikop dibuat : {perikop}\n"
            "ayat diproses  : {ayat} (baru: {ayat_baru})\n"
            "varian dibuat  : {varian}\n"
            "gagal          : {dilewati}\n\n"
            "Catatan: chunking & embedding TIDAK dijalankan pada tahap ini.\n"
        ).format(**jumlah)
        if galat:
            teks += "\nGalat:\n" + "\n".join("- " + g for g in galat[:10])
            if len(galat) > 10:
                teks += "\n- … dan %d lainnya" % (len(galat) - 10)
        return teks + "\n\nSumber:\n" + rincian
