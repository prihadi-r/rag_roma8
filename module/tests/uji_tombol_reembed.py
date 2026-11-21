import time
print("=== TOMBOL Re-embed (aksi manual) ===")
v = env['rag.verse'].search([('chapter','=',8),('verse_no','=',1)], limit=1)
c = v.chunk_ids[:1]
print("sebelum:", c.state, "| embedded_at:", c.embedded_at)
v.write({'ind': v.ind + ' (uji)'})   # menandai kotor
print("setelah edit → chunk.dirty:", c.dirty, "| ayat:", v.state)
t0 = time.time()
v.action_reembed_chunks()
print("aksi selesai %.2f detik" % (time.time() - t0))
c.invalidate_recordset(); v.invalidate_recordset()
print("sesudah:", c.state, "| dirty:", c.dirty, "| ayat:", v.state, "| embedded_at:", c.embedded_at)
env.cr.rollback()
print("(rollback)")
