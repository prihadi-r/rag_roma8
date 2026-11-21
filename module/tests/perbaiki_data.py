import json, hashlib
data = json.load(open('/opt/odoo18/rag-data/roma8.json', encoding='utf-8'))
sumber = {a['verse']: a for a in data['ayat']}

print("=== bandingkan hash ayat di DB vs dataset ===")
beda = []
for v in env['rag.verse'].search([('chapter','=',8)], order='verse_no'):
    acuan = sumber[v.verse_no]
    if v.content_hash != acuan['content_hash']:
        beda.append(v.verse_no)
print("ayat tidak cocok:", beda or "tidak ada")

if beda:
    print("memperbaiki lewat wizard impor…")
    wiz = env['rag.import.wizard'].create({})
    wiz.action_import()
    env.cr.commit()
    print("impor ulang selesai:", wiz.batch_id.rows_ok, "ayat")
    stat = env['rag.chunker'].run(hanya_kotor=True)
    print("chunking:", stat['chunk'], "chunk, gagal:", stat['gagal'])
    env.cr.commit()
    stat2 = env['rag.chunk']._cron_embed(limit=64)
    print("embedding:", stat2['berhasil'], "berhasil, gagal:", stat2['gagal'])

v1 = env['rag.verse'].search([('chapter','=',8),('verse_no','=',1)], limit=1)
print("\nAYT 8:1 sekarang:", v1.ind)
print("state ayat:", v1.state, "| chunk:", v1.chunk_ids[:1].state)
