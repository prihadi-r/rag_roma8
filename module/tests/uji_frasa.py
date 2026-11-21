from odoo.addons.rag_teologi.models.embedding_client import embed_texts
cfg = env['rag.config'].get_active(); model = cfg.embedding_model_id

frasa = [
    "Bagaimana pandangan Paulus mengenai keselamatan?",
    "Apa maksud Paulus tentang predestinasi dan rencana Allah?",
    "Allah menetapkan sejak semula supaya menjadi serupa dengan Anak-Nya",
    "rantai emas keselamatan dari dipanggil sampai dimuliakan",
    "Jelaskan Roma 8:28-30",
]
print(f"{'frasa':58} {'rank 8:29':>9} {'rank 8:30':>9}")
for f in frasa:
    vec = embed_texts(model.endpoint, model.api_model, [f], timeout=30)[0]
    lit = '[' + ','.join('%.7g' % float(x) for x in vec) + ']'
    env.cr.execute("""
      with s as (select v.verse_no, row_number() over (order by c.embedding <=> %s::vector) as rnk
                 from rag_chunk c join rag_verse v on v.id=c.verse_id)
      select verse_no, rnk from s where verse_no in (29,30)
    """, (lit,))
    d = dict(env.cr.fetchall())
    print(f"{f[:55]:58} {d.get(29,'-'):>9} {d.get(30,'-'):>9}")
