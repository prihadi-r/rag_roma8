from odoo.addons.rag_teologi.models.embedding_client import embed_texts
Svc = env['rag.query.service']
q = env['rag.query.log'].browse(20).question
cfg = env['rag.config'].get_active(); model = cfg.embedding_model_id
vec = embed_texts(model.endpoint, model.api_model, [q], timeout=30)[0]
lit = '[' + ','.join('%.7g' % float(x) for x in vec) + ']'

env.cr.execute("""
  with semua as (
    select v.ref_label,
           row_number() over (order by c.embedding <=> %s::vector) as rnk,
           (1-(c.embedding <=> %s::vector)) as cos
    from rag_chunk c join rag_verse v on v.id=c.verse_id
  )
  select rnk, ref_label, round(cos::numeric,4) from semua where rnk <= 25 order by rnk
""", (lit, lit))
baris = env.cr.fetchall()
print("peringkat dense 1..25:")
for rnk, ref, cos in baris:
    tanda = "   ← golden chain" if ref in ('Roma 8:29', 'Roma 8:30') else ""
    print(f"  {rnk:2}. {ref:11} cos={cos}{tanda}")

env.cr.execute("""
  with semua as (
    select v.ref_label, row_number() over (order by c.embedding <=> %s::vector) as rnk
    from rag_chunk c join rag_verse v on v.id=c.verse_id
  )
  select ref_label, rnk from semua where ref_label in ('Roma 8:29','Roma 8:30') order by rnk
""", (lit,))
print("\nperingkat global 29 & 30:", env.cr.fetchall())
