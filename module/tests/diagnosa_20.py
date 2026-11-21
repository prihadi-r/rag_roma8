from odoo.addons.rag_teologi.models.embedding_client import embed_texts
from odoo.addons.rag_teologi.models.query_service import RagQueryService

Svc = env['rag.query.service']
q = env['rag.query.log'].browse(20).question
cfg = env['rag.config'].get_active(); model = cfg.embedding_model_id
print("pertanyaan:", q)
print("tsquery   :", repr(Svc._tsquery(q)))
env.cr.execute("select count(*) from rag_chunk where fts_id @@ to_tsquery('simple', %s)", (Svc._tsquery(q),))
print("chunk cocok FTS:", env.cr.fetchone()[0])

vec = embed_texts(model.endpoint, model.api_model, [q], timeout=30)[0]
lit = '[' + ','.join('%.7g' % float(x) for x in vec) + ']'
env.cr.execute("""
  select v.ref_label, row_number() over (order by c.embedding <=> %s::vector) as rnk,
         round((1-(c.embedding <=> %s::vector))::numeric,4) as cos
  from rag_chunk c join rag_verse v on v.id=c.verse_id
  order by c.embedding <=> %s::vector limit 15
""", (lit, lit, lit))
print("\nperingkat dense (15 teratas):")
for ref, rnk, cos in env.cr.fetchall():
    tanda = "  ← golden chain" if ref in ('Roma 8:29', 'Roma 8:30') else ""
    print(f"   {rnk:2}. {ref:11} cos={cos}{tanda}")

env.cr.execute("""
  select v.ref_label, row_number() over (order by c.embedding <=> %s::vector) as rnk
  from rag_chunk c join rag_verse v on v.id=c.verse_id
  where v.verse_no in (29,30)
""", (lit,))
print("\nposisi 8:29 & 8:30:", env.cr.fetchall())
