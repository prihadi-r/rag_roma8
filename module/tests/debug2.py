c = env['rag.chunk'].search([], limit=1)
cid = c.id
env.cr.execute("select state, dirty, embedded_at from rag_chunk where id=%s", (cid,))
print("awal:", env.cr.fetchone())

print("--- uji UPDATE mentah ---")
env.cr.execute("UPDATE rag_chunk SET state='embedded', dirty=false, embedded_at=now() WHERE id=%s", (cid,))
env.cr.execute("select state, dirty, embedded_at from rag_chunk where id=%s", (cid,))
print("setelah update mentah:", env.cr.fetchone())

print("--- uji _tulis_vektor langsung ---")
model = env['rag.config'].get_active().embedding_model_id
vec = [0.001] * model.dimensions
c._tulis_vektor(model, [vec])
env.cr.execute("select state, dirty, embedded_at from rag_chunk where id=%s", (cid,))
print("setelah _tulis_vektor:", env.cr.fetchone())

print("--- uji write() ORM ---")
c.write({'state': 'chunked', 'dirty': True})
env.cr.execute("select state, dirty from rag_chunk where id=%s", (cid,))
print("setelah write chunked:", env.cr.fetchone())
env.cr.rollback()
