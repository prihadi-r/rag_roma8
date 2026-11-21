from odoo.addons.rag_teologi.models.embedding_client import embed_texts

cfg = env['rag.config'].get_active()
model = cfg.embedding_model_id
kueri = "pengangkatan menjadi anak Allah"
vec = embed_texts(model.endpoint, model.api_model or model.name, [kueri], timeout=30)[0]
lit = '[' + ','.join('%.7g' % float(x) for x in vec) + ']'

print("=== RRF: apakah 8:23 terangkat? ===")
env.cr.execute("""
WITH dense AS (
  SELECT c.id, row_number() OVER (ORDER BY c.embedding <=> %(v)s::vector) AS rnk
  FROM rag_chunk c ORDER BY c.embedding <=> %(v)s::vector LIMIT 20
), fts AS (
  SELECT c.id, row_number() OVER (
      ORDER BY ts_rank_cd(c.fts_id, q) + ts_rank_cd(c.fts_en, q) + ts_rank_cd(c.fts_gr, q) DESC) AS rnk
  FROM rag_chunk c, plainto_tsquery('simple', %(q)s) q
  WHERE c.fts_id @@ q OR c.fts_en @@ q OR c.fts_gr @@ q LIMIT 20
)
SELECT v.ref_label, d.rnk AS dense, f.rnk AS fts,
       round((1.0/(60+coalesce(d.rnk,1000)) + 1.0/(60+coalesce(f.rnk,1000)))::numeric, 5) AS rrf
FROM dense d FULL OUTER JOIN fts f ON d.id=f.id
JOIN rag_chunk c ON c.id=coalesce(d.id,f.id)
JOIN rag_verse v ON v.id=c.verse_id
ORDER BY rrf DESC LIMIT 5
""", {'v': lit, 'q': kueri})
for r in env.cr.fetchall():
    print(f"   RRF {r[3]:.5f}  {r[0]:12} (dense={r[1]}, fts={r[2]})")

print()
print("=== UJI JALUR GALAT (endpoint mati) ===")
chunk = env['rag.chunk'].search([], limit=1)
asli = model.endpoint
model.write({'endpoint': 'http://127.0.0.1:9/v1/embeddings'})
stat = chunk._embed()
print("berhasil:", stat['berhasil'], "| gagal:", stat['gagal'])
print("retry_count:", chunk.retry_count, "| state:", chunk.state)
print("last_error:", (chunk.last_error or '')[:120])
model.write({'endpoint': asli})
stat2 = chunk._embed()
print("setelah endpoint benar → berhasil:", stat2['berhasil'], "| retry:", chunk.retry_count, "| state:", chunk.state)
env.cr.rollback()
print("(rollback — data asli utuh)")
