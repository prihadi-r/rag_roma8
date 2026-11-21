print("=== uji dirty flag pada chunk nyata ===")
v = env['rag.verse'].search([('chapter','=',8),('verse_no','=',5)], limit=1)
c = v.chunk_ids[:1]
print("awal   : verse:", v.state, "| chunk.dirty:", c.dirty)
hash_lama = c.embed_hash
v.write({'ind': (v.ind or '') + ' [diubah untuk uji]'})
print("diedit : verse:", v.state, "| chunk.dirty:", c.dirty, "| perlu re-embed:", c.dirty)
stat = env['rag.chunker'].run(verses=v)
print("chunk ulang:", stat['chunk'], "| hash berubah:", c.embed_hash != hash_lama)
print("setelah: verse:", v.state, "| chunk.state:", c.state, "| chunk.dirty:", c.dirty)
env.cr.rollback()
print("(rollback — data asli utuh)")
