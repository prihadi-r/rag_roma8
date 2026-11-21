"""Layanan Kueri RAG: router, hybrid search (RRF), context builder, LLM.

Bagian inti Fase 7. Tidak menyimpan commit sendiri; pemanggil yang mengatur.
"""
import logging
import re
import time

import requests

from odoo import api, models
from odoo.exceptions import UserError

from . import morph
from .embedding_client import EmbeddingError, embed_texts

_logger = logging.getLogger(__name__)

#: Kata yang dibuang saat membangun tsquery agar tidak meng-AND seluruh kalimat.
STOPWORDS = {
    'apa', 'apakah', 'yang', 'dan', 'di', 'ke', 'dari', 'dalam', 'pada', 'untuk',
    'dengan', 'adalah', 'itu', 'ini', 'bagaimana', 'mengapa', 'kenapa', 'siapa',
    'jelaskan', 'sebutkan', 'tolong', 'bagaimanakah', 'seperti', 'tentang',
    'the', 'a', 'an', 'of', 'to', 'in', 'is', 'are', 'what', 'how', 'why',
    'does', 'do', 'and', 'for', 'with', 'that', 'this',
}

#: "Roma 8:1", "8:1-11", "Rm 8:1"
_POLA_AYAT = re.compile(
    r'\b(?:roma|rom|rm)?\s*8\s*[:.]\s*(\d{1,2})(?:\s*[-–]\s*(\d{1,2}))?\b',
    re.IGNORECASE,
)


class RagQueryService(models.AbstractModel):
    _name = 'rag.query.service'
    _description = 'Layanan Kueri RAG'

    # ------------------------------------------------------------- router
    @api.model
    def deteksi_ayat(self, pertanyaan):
        """Kembalikan daftar nomor ayat bila pertanyaan menyebut referensi."""
        cocok = _POLA_AYAT.search(pertanyaan or '')
        if not cocok:
            return []
        awal = int(cocok.group(1))
        akhir = int(cocok.group(2)) if cocok.group(2) else awal
        if akhir < awal or akhir - awal > 20:
            return [awal]
        return list(range(awal, akhir + 1))

    # ---------------------------------------------------------- tsquery
    @api.model
    def _tsquery(self, pertanyaan):
        """Bangun tsquery OR + perluas dengan sinonim teologis.

        Kembalikan (tsquery, daftar_padanan). Padanan dicatat di riwayat agar
        keputusan pencarian bisa diaudit.
        """
        kata = [
            k for k in re.findall(r'[0-9a-zA-Z\u0370-\u03ff\u1f00-\u1fff]{3,}', pertanyaan or '')
            if k.lower() not in STOPWORDS
        ]
        if not kata:
            kata = re.findall(r'[0-9a-zA-Z\u0370-\u03ff\u1f00-\u1fff]{2,}', pertanyaan or '')

        padanan = []
        if kata:
            Expansion = self.env['rag.query.expansion']
            for istilah in dict.fromkeys(k.lower() for k in kata):
                for exp in Expansion.search([('term', '=ilike', istilah), ('active', '=', True)]):
                    for baris in exp.line_ids:
                        for kata_padanan in re.findall(
                                r'[0-9a-zA-Z\u0370-\u03ff\u1f00-\u1fff]{3,}', baris.word or ''):
                            if kata_padanan.lower() not in STOPWORDS:
                                padanan.append(kata_padanan)

        semua = list(dict.fromkeys(kata + padanan))
        return ' | '.join(semua), padanan

    # ------------------------------------------------------------- kueri
    @api.model
    def ask(self, pertanyaan, config=None):
        """Buat record riwayat lalu langsung jalankan."""
        pertanyaan = (pertanyaan or '').strip()
        if not pertanyaan:
            raise UserError("Pertanyaan tidak boleh kosong.")
        log = self.env['rag.query.log'].create({
            'question': pertanyaan,
            'config_id': (config or self.env['rag.config'].get_active()).id,
        })
        return self._jalankan(log)

    @api.model
    def _jalankan(self, log):
        """Eksekusi satu record rag.query.log (dipakai tombol & konsol)."""
        pertanyaan = (log.question or '').strip()
        if not pertanyaan:
            raise UserError("Pertanyaan tidak boleh kosong.")

        cfg = log.config_id or self.env['rag.config'].get_active()
        if not cfg:
            raise UserError("Belum ada konfigurasi RAG yang aktif.")
        model = cfg.embedding_model_id
        if not model:
            raise UserError("Konfigurasi RAG belum menunjuk model embedding.")

        # Vektor di database dibuat oleh model tertentu. Memakai konfigurasi
        # dengan model/dimensi lain akan membandingkan ruang vektor berbeda.
        self.env.cr.execute(
            "SELECT DISTINCT embedding_model_id FROM rag_chunk WHERE embedding IS NOT NULL")
        dipakai = {r[0] for r in self.env.cr.fetchall() if r[0]}
        if dipakai and dipakai != {model.id}:
            nama = ', '.join(
                self.env['rag.embedding.model'].browse(m).display_name for m in dipakai)
            raise UserError(
                "Konfigurasi '%s' memakai model embedding '%s', sedangkan chunk "
                "di-embed dengan '%s'. Pilih konfigurasi yang modelnya sama, atau "
                "jalankan re-embedding terlebih dahulu."
                % (cfg.name, model.name, nama))

        ayat = self.deteksi_ayat(pertanyaan)
        route_code = 'direct' if ayat else 'hybrid'
        route = self.env['rag.query.route'].search([('code', '=', route_code)], limit=1)

        if log.hit_ids:
            log.hit_ids.unlink()
        log.write({
            'state': 'running',
            'error': False,
            'answer': False,
            'citations': False,
            'config_id': cfg.id,
            'route_id': route.id if route else False,
            'params': {
                'top_k_dense': cfg.top_k_dense,
                'top_k_fts': cfg.top_k_fts,
                'rrf_k': cfg.rrf_k,
                'top_k_final': cfg.top_k_final,
                'temperature': cfg.temperature,
                'route': route_code,
            },
        })
        # supaya state 'running' benar-benar sampai ke DB sebelum proses panjang
        self.env.flush_all()

        stage = {}
        mulai = time.time()
        try:
            if route_code == 'direct' and ayat:
                hasil = self._cari_langsung(ayat, cfg, stage)
            else:
                hasil = self._cari_hybrid(pertanyaan, cfg, model, stage)

            konteks = self._bangun_konteks(hasil, cfg)
            # hanya nilai numerik yang dijumlahkan (stage juga memuat daftar padanan)
            angka = sum(v for v in stage.values() if isinstance(v, (int, float)))
            stage['context_ms'] = max(0, int((time.time() - mulai) * 1000) - angka)

            t0 = time.time()
            jawaban, usage = self._panggil_llm(pertanyaan, konteks, cfg)
            stage['generate_ms'] = int((time.time() - t0) * 1000)

            log.write({
                'answer': jawaban,
                'citations': [
                    {'verse': h['ref'], 'score': round(h['rrf'], 6), 'injected': h['injected']}
                    for h in hasil
                ],
                'latency_ms': int((time.time() - mulai) * 1000),
                'stage_ms': stage,
                'prompt_tokens': usage.get('prompt_tokens', 0),
                'completion_tokens': usage.get('completion_tokens', 0),
                'state': 'success',
            })
            for pos, h in enumerate(hasil, start=1):
                self.env['rag.query.hit'].create({
                    'query_id': log.id,
                    'chunk_id': h['chunk_id'],
                    'rank_dense': h['rank_dense'],
                    'rank_fts': h['rank_fts'],
                    'score_dense': h['score_dense'],
                    'score_fts': h['score_fts'],
                    'rrf_score': h['rrf'],
                    'position': pos,
                    'injected': h['injected'],
                })
        except Exception as exc:  # noqa: BLE001
            log.write({
                'state': 'error',
                'error': "%s: %s" % (type(exc).__name__, exc),
                'latency_ms': int((time.time() - mulai) * 1000),
                'stage_ms': stage,
            })
            _logger.exception("Kueri RAG gagal: %s", pertanyaan)
            raise
        return log

    # --------------------------------------------------- pencarian langsung
    @api.model
    def _cari_langsung(self, ayat, cfg, stage):
        t0 = time.time()
        chunks = self.env['rag.chunk'].search([
            ('verse_id.chapter', '=', 8),
            ('verse_id.verse_no', 'in', ayat),
        ])
        stage['search_ms'] = int((time.time() - t0) * 1000)
        return [{
            'chunk_id': c.id,
            'ref': c.verse_id.ref_label,
            'chunk': c,
            'rank_dense': False,
            'rank_fts': False,
            'score_dense': 0.0,
            'score_fts': 0.0,
            'rrf': 1.0,
            'injected': True,
        } for c in chunks]

    # ------------------------------------------------------ pencarian hybrid
    @api.model
    def _cari_hybrid(self, pertanyaan, cfg, model, stage):
        t0 = time.time()
        try:
            vec = embed_texts(
                endpoint=model.endpoint,
                api_model=model.api_model or model.name,
                texts=[pertanyaan],
                timeout=cfg.timeout_embed_s or 30,
            )[0]
        except EmbeddingError as exc:
            raise UserError("Gagal membuat embedding pertanyaan: %s" % exc) from exc
        stage['embed_ms'] = int((time.time() - t0) * 1000)

        literal = '[' + ','.join('%.7g' % float(x) for x in vec) + ']'
        tsq, padanan = self._tsquery(pertanyaan)
        stage['fts_terms'] = len(tsq.split(' | '))
        if padanan:
            stage['expanded'] = padanan
        t0 = time.time()
        self.env.cr.execute("""
            WITH dense AS (
                SELECT c.id,
                       row_number() OVER (ORDER BY c.embedding <=> %(v)s::vector) AS rnk,
                       (1 - (c.embedding <=> %(v)s::vector)) AS skor
                FROM rag_chunk c
                WHERE c.active AND c.embedding IS NOT NULL
                ORDER BY c.embedding <=> %(v)s::vector
                LIMIT %(kd)s
            ), fts AS (
                SELECT c.id,
                       row_number() OVER (ORDER BY ts_rank_cd(c.fts_id, q) + ts_rank_cd(c.fts_en, q)
                                                   + ts_rank_cd(c.fts_gr, q) DESC) AS rnk,
                       ts_rank_cd(c.fts_id, q) + ts_rank_cd(c.fts_en, q) + ts_rank_cd(c.fts_gr, q) AS skor
                FROM rag_chunk c, to_tsquery('simple', %(q)s) q
                WHERE c.active AND (c.fts_id @@ q OR c.fts_en @@ q OR c.fts_gr @@ q)
                LIMIT %(kf)s
            )
            SELECT coalesce(d.id, f.id) AS id, d.rnk, f.rnk, d.skor, f.skor,
                   (1.0/(%(rrf)s + coalesce(d.rnk, 1000))
                  + 1.0/(%(rrf)s + coalesce(f.rnk, 1000))) AS rrf
            FROM dense d FULL OUTER JOIN fts f ON d.id = f.id
            ORDER BY rrf DESC
            LIMIT %(kfinal)s
        """, {
            'v': literal, 'q': tsq, 'kd': cfg.top_k_dense, 'kf': cfg.top_k_fts,
            'rrf': cfg.rrf_k, 'kfinal': cfg.top_k_final,
        })
        baris = self.env.cr.fetchall()
        stage['search_ms'] = int((time.time() - t0) * 1000)

        Chunk = self.env['rag.chunk']
        hasil = []
        for urut, (cid, rnk_d, rnk_f, skor_d, skor_f, rrf) in enumerate(baris):
            chunk = Chunk.browse(cid)
            hasil.append({
                'chunk_id': cid,
                'ref': chunk.verse_id.ref_label,
                'chunk': chunk,
                'rank_dense': rnk_d,
                'rank_fts': rnk_f,
                'score_dense': float(skor_d or 0.0),
                'score_fts': float(skor_f or 0.0),
                'rrf': float(rrf),
                'injected': urut < (cfg.top_k_final or 5),
            })
        return hasil

    # ------------------------------------------------------- context builder
    @api.model
    def _baris_morfologi(self, verse, maks=10):
        """Ringkas parsing kata isi (nomina/verba/adjektiva) agar LLM tidak menebak."""
        penting = {'nomina', 'verba', 'adjektiva'}
        potongan = []
        for kata in verse.words or []:
            hasil = morph.decode(kata.get('morph'))
            if hasil.get('pos') not in penting:
                continue
            potongan.append("%s (G%s) %s" % (kata.get('surface'), kata.get('strongs'), hasil['text']))
            if len(potongan) >= maks:
                break
        return ' | '.join(potongan)

    @api.model
    def _baris_ayat(self, verse, ringkas=False):
        """Satu blok ayat. `ringkas` dipakai untuk ayat konteks (bukan hasil cari)."""
        baris = []
        if ringkas:
            baris.append("[%s] AYT: %s" % (verse.ref_label, verse.ind or '-'))
        else:
            baris.append("\n[%s]" % verse.ref_label)
            if verse.greek_accented:
                baris.append("Yunani : %s" % verse.greek_accented)
            if verse.kjv:
                baris.append("KJV    : %s" % verse.kjv)
            if verse.ind:
                baris.append("AYT    : %s" % verse.ind)
            morf = self._baris_morfologi(verse)
            if morf:
                baris.append("Morf   : %s" % morf)
        return baris

    @api.model
    def _bangun_konteks(self, hasil, cfg):
        """Konteks = ayat terambil (rinci) + konteks perikop secukupnya.

        Aturan (PLAN §5: parent = perikop, tetapi tetap hemat token):
        * perikop dari **hit peringkat 1** disertakan utuh — di sinilah alur
          argumen biasanya berada (mis. "golden chain" 8:29–30 di 8:18–30);
        * perikop lain hanya menyertakan ayat terambil + tetangga ±1 ayat;
        * blok varian dihitung lebih dulu agar tidak terpotong.
        """
        terambil = {h['chunk'].verse_id.id: h for h in hasil if h['injected']}
        if not terambil:
            return ""

        urut = [h for h in hasil if h['injected']]
        utama = urut[0]['chunk'].pericope_id

        perikop = {}
        for h in urut:
            p = h['chunk'].pericope_id
            if p:
                perikop[p.id] = p

        # --- ayat yang disertakan per perikop
        rencana = {}
        for pid, p in perikop.items():
            ayat_per = p.verse_ids.sorted('verse_no')
            if utama and pid == utama.id:
                rencana[pid] = list(ayat_per)
            else:
                nomor = {h['chunk'].verse_id.verse_no for h in urut
                         if h['chunk'].pericope_id.id == pid}
                lebar = set()
                for n in nomor:
                    lebar.update({n - 1, n, n + 1})
                rencana[pid] = [v for v in ayat_per if v.verse_no in lebar]

        # --- blok varian lebih dulu, agar tidak termakan pemotongan
        varian_blok = []
        for pid, ayat_list in rencana.items():
            for verse in ayat_list:
                for va in verse.variant_ids:
                    if not va.is_significant:
                        continue
                    saksi = va.witness_id.code or '?'
                    jenis = va.variant_type_id.code or '?'
                    if jenis == 'omission':
                        varian_blok.append(
                            "%s — %s MENGHILANGKAN klausa \"%s\"; klausa itu ADA pada bacaan Byzantine"
                            % (verse.ref_label, saksi, va.byz_text))
                    elif jenis == 'addition':
                        varian_blok.append(
                            "%s — %s MENAMBAHKAN \"%s\"" % (verse.ref_label, saksi, va.other_text))
                    else:
                        varian_blok.append(
                            "%s — %s membaca \"%s\"; Byzantine: \"%s\""
                            % (verse.ref_label, saksi, va.other_text, va.byz_text))

        kepala = [
            "[SUMBER] Yunani: Robinson-Pierpont 2018 (Byzantine Textform). "
            "Inggris: KJV 1769. Indonesia: AYT (Alkitab Yang Terbuka) — bukan TB/LAI.",
            "[CARA BACA] Ayat bertanda ▶ adalah hasil pencarian. Ayat lain dalam "
            "perikop yang sama disertakan sebagai konteks agar alur argumen tidak terputus.",
        ]
        ekor = []
        if varian_blok:
            ekor = ["\n[VARIAN TEKSTUAL]",
                    "Ayat-ayat berikut MEMILIKI varian; sebutkan bila relevan:"] + varian_blok

        batas = cfg.context_budget_chars or 6000
        sisa = batas - len("\n".join(kepala)) - len("\n".join(ekor)) - 10

        blok = list(kepala)
        for pid, p in perikop.items():
            judul = (p.name or '').split(' — ')[0] if p.name else ''
            kepala_per = ["\n[PERIKOP %s — %s]" % (judul, p.title_id or '')]
            if p.summary_id:
                kepala_per.append(p.summary_id)
            if len("\n".join(kepala_per)) > sisa:
                continue
            blok.extend(kepala_per)
            sisa -= len("\n".join(kepala_per))

            for verse in rencana[pid]:
                diambil = verse.id in terambil
                if diambil:
                    bagian = ["[▶ %s]  (hasil pencarian, skor RRF %.5f)"
                              % (verse.ref_label, terambil[verse.id]['rrf'])]
                    bagian.extend(self._baris_ayat(verse, ringkas=False))
                else:
                    bagian = self._baris_ayat(verse, ringkas=True)
                panjang = len("\n".join(bagian)) + 1
                if panjang > sisa:
                    blok.append("[… konteks dipotong karena batas %d karakter]" % batas)
                    sisa = 0
                    break
                blok.extend(bagian)
                sisa -= panjang
            if sisa <= 0:
                break

        blok.extend(ekor if len("\n".join(ekor)) <= batas else [])
        teks = "\n".join(blok)
        if len(teks) > batas:
            _logger.warning("Konteks melebihi batas: %d > %d", len(teks), batas)
        return teks

    # ---------------------------------------------------------------- LLM
    @api.model
    def _panggil_llm(self, pertanyaan, konteks, cfg):
        sistem = cfg.prompt_template_id.body or (
            "Jawab HANYA berdasarkan konteks. Sebutkan nomor ayat dan kutip kata persis.")
        pesan = [
            {'role': 'system', 'content': sistem},
            {'role': 'user', 'content': "KONTEKS:\n%s\n\nPERTANYAAN: %s" % (konteks, pertanyaan)},
        ]
        url = cfg.chat_base_url.rstrip('/') + '/chat/completions'
        try:
            resp = requests.post(url, json={
                'model': cfg.chat_model,
                'messages': pesan,
                'temperature': cfg.temperature,
                'max_tokens': cfg.max_tokens,
                'stream': False,
            }, timeout=cfg.timeout_chat_s or 180)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:  # noqa: BLE001
            raise UserError("Gagal memanggil layanan chat: %s" % exc) from exc

        jawaban = (data.get('choices') or [{}])[0].get('message', {}).get('content', '')
        usage = data.get('usage') or {}
        return jawaban.strip(), usage
