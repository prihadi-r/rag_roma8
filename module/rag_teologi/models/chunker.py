"""Chunking engine: menyusun unit pencarian + teks embedding.

Tidak memanggil HTTP embedding — vektor diisi pada Fase 6.
"""
import hashlib
import json
import logging
import os

from odoo import api, models

from . import morph

_logger = logging.getLogger(__name__)

_GLOSS = None


def _gloss():
    """Muat glos Strong's sekali per worker (public domain)."""
    global _GLOSS
    if _GLOSS is None:
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'data', 'strongs_greek.json',
        )
        if not os.path.exists(path):
            _logger.warning("Glos Strong's tidak ditemukan: %s", path)
            _GLOSS = {}
        else:
            with open(path, encoding='utf-8') as fh:
                _GLOSS = json.load(fh).get('entri', {})
    return _GLOSS


class RagChunker(models.AbstractModel):
    _name = 'rag.chunker'
    _description = 'Chunking Engine'

    # ------------------------------------------------------------------ teks
    @api.model
    def build_embed_text(self, verse):
        """Komposisi deterministik: Indonesia, Inggris, Yunani, transliterasi, lema, glos.

        Yunani berdiakritik sengaja tidak dipakai (lemah pada model embedding
        multibahasa) — dipakai bentuk tanpa aksen + transliterasi.
        """
        gloss = _gloss()
        lema, glos = [], []
        for kata in verse.words or []:
            sid = str(kata.get('strongs') or '').strip()
            if not sid:
                continue
            entri = gloss.get(sid) or {}
            if entri.get('lemma') and entri['lemma'] not in lema:
                lema.append(entri['lemma'])
            # Glos Strong's bergaya konkordansi ("any, aught, man, neither any").
            # Ambil dua pengertian pertama saja agar tidak mendominasi embedding.
            for pengertian in (entri.get('gloss') or '').split(',')[:2]:
                bersih = pengertian.strip().strip('.;')
                if (bersih and len(bersih) > 2 and not bersih.startswith('X ')
                        and bersih.lower() not in [g.lower() for g in glos]):
                    glos.append(bersih)

        baris = [
            ('ID', verse.ind),
            ('EN', verse.kjv),
            ('YUNANI', verse.greek_stripped),
            ('TRANS', verse.transliteration),
            ('LEMA', ' '.join(lema[:60])),
            ('GLOSS', ', '.join(glos[:25])[:700]),
        ]
        return '\n'.join(f"{label}: {isi.strip()}" for label, isi in baris if isi and isi.strip())

    @api.model
    def morph_tokens(self, verse):
        """Kode morfologi yang sudah diterjemahkan, untuk indeks full-text."""
        token = set()
        for kata in verse.words or []:
            for kode in [kata.get('morph')] + [a.get('morph') for a in (kata.get('alt') or [])]:
                hasil = morph.decode(kode)
                for kunci in ('pos', 'tense', 'voice', 'mood', 'case', 'number', 'gender'):
                    nilai = hasil.get(kunci)
                    if nilai:
                        token.add(nilai.replace(' ', '_'))
        return sorted(token)

    @api.model
    def build_lexeme_text(self, verse):
        gloss = _gloss()
        lema = []
        for kata in verse.words or []:
            entri = gloss.get(str(kata.get('strongs') or '')) or {}
            if entri.get('lemma') and entri['lemma'] not in lema:
                lema.append(entri['lemma'])
        return ' '.join(lema)

    # ---------------------------------------------------------------- chunk
    @api.model
    def chunk_verse(self, verse):
        kind = self.env['rag.chunk.kind'].search([('code', '=', 'verse')], limit=1)
        if not kind:
            raise ValueError("Master 'rag.chunk.kind' dengan kode 'verse' tidak ada.")

        embed_text = self.build_embed_text(verse)
        lexeme_text = ' '.join(
            [self.build_lexeme_text(verse)] + self.morph_tokens(verse)
        ).strip()
        vals = {
            'verse_id': verse.id,
            'pericope_id': verse.pericope_id.id,
            'chunk_kind_id': kind.id,
            'seq': verse.verse_no,
            'lai_text': verse.ind,
            'kjv_text': verse.kjv,
            'greek_stripped': verse.greek_stripped,
            'lexeme_text': lexeme_text,
            'embed_text': embed_text,
            'embed_hash': hashlib.sha256(embed_text.encode('utf-8')).hexdigest(),
            'token_est': max(1, len(embed_text) // 4),
            'state': 'chunked',
            'dirty': True,          # menunggu embedding (Fase 6)
        }
        chunk = self.env['rag.chunk'].search([
            ('verse_id', '=', verse.id),
            ('chunk_kind_id', '=', kind.id),
        ], limit=1)
        if chunk:
            chunk.write(vals)
        else:
            chunk = self.env['rag.chunk'].create(vals)

        if verse.state != 'chunked':
            verse.write({'state': 'chunked'})
        return chunk

    @api.model
    def run(self, verses=None, hanya_kotor=True):
        """Chunking massal. Mengembalikan dict statistik."""
        if verses is None:
            domain = [('active', '=', True)]
            if hanya_kotor:
                domain += ['|', ('state', 'in', ('draft', 'error')), ('dirty', '=', True)]
            verses = self.env['rag.verse'].search(domain)

        stat = {'ayat': 0, 'chunk': 0, 'gagal': 0, 'galat': []}
        for verse in verses:
            try:
                with self.env.cr.savepoint():
                    self.chunk_verse(verse)
                stat['ayat'] += 1
                stat['chunk'] += 1
            except Exception as exc:  # noqa: BLE001
                stat['gagal'] += 1
                pesan = "8:%s → %s: %s" % (
                    verse.verse_no, type(exc).__name__, str(exc).strip().replace("\n", " "))
                stat['galat'].append(pesan)
                _logger.warning("Chunking Roma 8:%s gagal: %s", verse.verse_no, exc)
        return stat
