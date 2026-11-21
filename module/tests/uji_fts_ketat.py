kueri_kata = ['pengangkatan', 'anak', 'allah']
print("=== mengapa plainto_tsquery gagal? ===")
env.cr.execute("select plainto_tsquery('simple', %s)::text", ('pengangkatan menjadi anak Allah',))
print("plainto (AND semua kata):", env.cr.fetchone()[0])
for kata in kueri_kata:
    env.cr.execute("""select count(*) from rag_chunk c join rag_verse v on v.id=c.verse_id
                      where c.fts_id @@ plainto_tsquery('simple', %s)""", (kata,))
    print(f"  '{kata}' → {env.cr.fetchone()[0]} chunk")

print()
print("=== FTS dengan OR antar kata ===")
env.cr.execute("""
select v.ref_label,
       ts_rank_cd(c.fts_id, to_tsquery('simple', %s)) as skor
from rag_chunk c join rag_verse v on v.id=c.verse_id
where c.fts_id @@ to_tsquery('simple', %s)
order by skor desc limit 5
""", ('pengangkatan | anak | allah', 'pengangkatan | anak | allah'))
for r in env.cr.fetchall():
    print(f"   {r[1]:.4f}  {r[0]}")

print()
print("=== RRF dengan FTS berbasis OR ===")
from odoo.addons.rag_teologi.models.embedding_client import embed_texts
cfg = env['rag.config'].get_active(); model = cfg.embedding_model_id
kueri = "pengangkatan menjadi anak Allah"
vec = embed_texts(model.endpoint, model.api_model, [kueri], timeout=30)[0]
lit = '[' + ','.join('%.7g' % float(x) for x in vec) + ']'
env.cr.execute("""
WITH dense AS (
  SELECT id, row_number() OVER (ORDER BY embedding <=> %(v)s::vector) AS rnk
  FROM rag_chunk ORDER BY embedding <=> %(v)s::vector LIMIT 20
), fts AS (
  SELECT id, row_number() OVER (ORDER BY ts_rank_cd(fts_id, q) DESC) AS rnk
  FROM rag_chunk, to_tsquery('simple', %(q)s) q
  WHERE fts_id @@ q LIMIT 20
)
SELECT v.ref_label, d.rnk, f.rnk,
       round((1.0/(60+coalesce(d.rnk,1000)) + 1.0/(60+coalesce(f.rnk,1000)))::numeric,5) AS rrf
FROM dense d FULL OUTER JOIN fts f ON d.id=f.id
JOIN rag_chunk c ON c.id=coalesce(d.id,f.id)
JOIN rag_verse v ON v.id=c.verse_id
ORDER BY rrf DESC LIMIT 5
""", {'v': lit, 'q': 'pengangkatan | anak | allah'})
for r in env.cr.fetchall():
    print(f"   RRF {r[3]:.5f}  {r[0]:12} (dense={r[1]}, fts={r[2]})")
