print("=== IMPOR DATASET ROMA 8 ===")
wiz = env['rag.import.wizard'].create({})
wiz.action_import()
env.cr.commit()
b = wiz.batch_id
print("batch:", b.name, "| state:", b.state, "| ok:", b.rows_ok, "| gagal:", b.rows_error)
print()
print(b.log[:2500])
print()
print("=== ISI DATABASE ===")
for nama in ('rag.book', 'rag.pericope', 'rag.verse', 'rag.variant', 'rag.chunk'):
    print(f"{nama:16}: {env[nama].search_count([])}")
