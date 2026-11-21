print("=== UJI IDEMPOTENSI: impor kedua ===")
sebelum = {m: env[m].search_count([]) for m in ('rag.book','rag.pericope','rag.verse','rag.variant','rag.chunk')}
print("sebelum:", sebelum)
wiz = env['rag.import.wizard'].create({})
wiz.action_import()
env.cr.commit()
b = wiz.batch_id
print("batch  :", b.state, "| ok:", b.rows_ok, "| gagal:", b.rows_error)
sesudah = {m: env[m].search_count([]) for m in ('rag.book','rag.pericope','rag.verse','rag.variant','rag.chunk')}
print("sesudah:", sesudah)
print("bertambah?", {k: sesudah[k]-sebelum[k] for k in sebelum if sesudah[k] != sebelum[k]} or "tidak ada duplikasi")
v = env['rag.verse'].search([('verse_no','=','1'),('chapter','=','8')], limit=1)
print("8:1 → varian:", v.variant_count, "| kata:", v.word_count, "| state:", v.state, "| dirty:", v.dirty)
