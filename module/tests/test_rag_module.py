"""Uji fungsional modul rag_teologi — dijalankan lewat `odoo-bin shell`.

    odoo-bin shell -c /etc/odoo18.conf -d rag_roma8 --no-http < scripts/test_rag_module.py

Seluruh data uji di-rollback di akhir; tidak meninggalkan jejak di database.
"""
print("=== UJI FUNGSIONAL MODUL rag_teologi ===")

book = env['rag.book'].create({'code': 'ROM', 'name_id': 'Roma', 'chapter_count': 16})
per = env['rag.pericope'].create({
    'book_id': book.id, 'chapter': 8, 'verse_start': 1, 'verse_end': 11,
    'title_id': 'Hidup oleh Roh', 'state': 'ready',
})
print("1. perikop      :", per.name)

v = env['rag.verse'].create({
    'book_id': book.id, 'pericope_id': per.id, 'chapter': 8, 'verse_no': 1,
    'greek_accented': 'Οὐδὲν ἄρα νῦν κατάκριμα',
    'greek_stripped': 'ουδεν αρα νυν κατακριμα',
    'kjv': 'There is therefore now no condemnation',
    'ind': 'Karena itu, sekarang tidak ada lagi penghukuman',
    'words': [{'surface': 'ουδεν', 'strongs': '3762', 'morph': 'A-NSN-N'}],
})
print("2. ayat         :", v.ref_label, "| kata:", v.word_count, "| state:", v.state, "| dirty:", v.dirty)

kind = env['rag.chunk.kind'].search([('code', '=', 'verse')])
ch = env['rag.chunk'].create({
    'verse_id': v.id, 'pericope_id': per.id, 'chunk_kind_id': kind.id,
    'lai_text': v.ind, 'kjv_text': v.kjv, 'greek_stripped': v.greek_stripped,
    'lexeme_text': 'G2631 κατακριμα', 'embed_text': v.ind + ' ' + v.kjv,
})
print("3. label chunk  :", repr(ch.label), "| display_name:", ch.display_name)

vec = '[' + ','.join(['0.01'] * 1024) + ']'
env.cr.execute(
    "UPDATE rag_chunk SET embedding=%s::vector, state='embedded', dirty=false WHERE id=%s",
    (vec, ch.id),
)
v.write({'state': 'embedded'})
env.invalidate_all()
print("4. setelah embed: verse =", v.state, "| chunk =", ch.state, "| chunk.dirty =", ch.dirty)

v.write({'ind': 'Teks diubah setelah embed'})
print("5. setelah edit : verse =", v.state, "| dirty =", v.dirty, "| chunk perlu re-embed =", ch.dirty)

env.cr.execute(
    "SELECT fts_id IS NOT NULL, fts_en IS NOT NULL, fts_gr IS NOT NULL, embedding IS NOT NULL "
    "FROM rag_chunk WHERE id=%s", (ch.id,),
)
print("6. kolom non-ORM (fts id/en/gr/vec):", env.cr.fetchone())
env.cr.execute("SELECT id FROM rag_chunk WHERE fts_gr @@ plainto_tsquery('simple','κατακριμα')")
print("7. full-text Yunani   :", env.cr.fetchall())
env.cr.execute("SELECT id FROM rag_chunk WHERE fts_id @@ plainto_tsquery('simple','penghukuman')")
print("8. full-text Indonesia:", env.cr.fetchall())
env.cr.execute(
    "SELECT id, round((1-(embedding <=> %s::vector))::numeric,4) FROM rag_chunk "
    "ORDER BY embedding <=> %s::vector LIMIT 1", (vec, vec),
)
print("9. cosine ke diri sendiri:", env.cr.fetchall())

w = env['rag.witness'].search([('code', '=', 'NA')], limit=1)
vt = env['rag.variant.type'].search([('code', '=', 'omission')], limit=1)
va = env['rag.variant'].create({
    'verse_id': v.id, 'seq': 1, 'clause_ref': '8:1b',
    'witness_id': w.id, 'variant_type_id': vt.id,
    'byz_text': 'μὴ κατὰ σάρκα περιπατοῦσιν ἀλλὰ κατὰ πνεῦμα', 'other_text': '-',
})
print("10. varian      :", va.verse_id.ref_label, va.witness_id.code, va.variant_type_id.code, "| jumlah:", v.variant_count)

q = env['rag.query.log'].create({
    'question': 'Apa itu κατάκριμα di Roma 8:1?',
    'route_id': env['rag.query.route'].search([('code', '=', 'hybrid')], limit=1).id,
    'config_id': env['rag.config'].get_active().id,
    'answer': 'uji', 'latency_ms': 1234,
})
env['rag.query.hit'].create({
    'query_id': q.id, 'chunk_id': ch.id, 'rank_dense': 1, 'rank_fts': 2,
    'score_dense': 0.83, 'score_fts': 0.21, 'rrf_score': 0.0325,
    'position': 1, 'injected': True,
})
print("11. query log   :", q.name, "| hit:", q.hit_count, "| user:", q.user_id.login)
print("12. config aktif:", env['rag.config'].get_active().name,
      "| model:", env['rag.config'].get_active().embedding_model_id.name)

# --- batasan database
for label, fn in [
    ("ayat ganda", lambda: env['rag.verse'].create({'book_id': book.id, 'chapter': 8, 'verse_no': 1})),
    ("dua config aktif", lambda: env['rag.config'].create({'name': 'Kedua', 'embedding_model_id': env['rag.embedding.model'].search([], limit=1).id})),
]:
    try:
        with env.cr.savepoint():
            fn()
        print(f"13. {label:18}: GAGAL — seharusnya ditolak")
    except Exception as exc:  # noqa: BLE001
        print(f"13. {label:18}: ditolak oleh database → {type(exc).__name__}")

env.cr.rollback()
print("=== SELESAI (rollback, data uji dibuang) ===")
