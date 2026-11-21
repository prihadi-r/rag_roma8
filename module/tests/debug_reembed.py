def db_state(cid):
    env.cr.execute("select state, dirty, retry_count, embedded_at is not null from rag_chunk where id=%s", (cid,))
    return env.cr.fetchone()

c = env['rag.chunk'].search([], limit=1)
cid = c.id
print("awal            :", db_state(cid))
c.write({'state': 'chunked', 'dirty': True, 'retry_count': 0, 'last_error': False})
print("setelah write() :", db_state(cid))
stat = c._embed()
print("_embed stat     :", stat)
print("setelah _embed  :", db_state(cid))
c.invalidate_recordset()
print("setelah invalid :", db_state(cid))
print("baca ORM        :", c.state, c.dirty)
env.cr.flush_all()
print("setelah flush   :", db_state(cid))
env.cr.rollback()
