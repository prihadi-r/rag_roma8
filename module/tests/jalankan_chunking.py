print("=== CHUNKING ROMA 8 ===")
Chunker = env['rag.chunker']
stat = Chunker.run(hanya_kotor=True)
env.cr.commit()
print("ayat diproses:", stat['ayat'], "| chunk:", stat['chunk'], "| gagal:", stat['gagal'])
for g in stat['galat'][:5]:
    print("  GALAT:", g)

print()
print("=== ISI ===")
print("chunk:", env['rag.chunk'].search_count([]))
for state in ('draft', 'chunked', 'embedded', 'error'):
    print(f"  ayat {state:9}: {env['rag.verse'].search_count([('state','=',state)])}")

v = env['rag.verse'].search([('chapter','=',8),('verse_no','=',1)], limit=1)
c = v.chunk_ids[:1]
print()
print("=== CHUNK Roma 8:1 ===")
print("label      :", c.label)
print("token_est  :", c.token_est)
print("embed_hash :", c.embed_hash)
print("state      :", c.state, "| dirty:", c.dirty)
print("lexeme_text:", c.lexeme_text)
print()
print("--- embed_text ---")
print(c.embed_text)
