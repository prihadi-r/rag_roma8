import json
data = json.load(open('/opt/odoo18/rag-data/roma8.json', encoding='utf-8'))
sumber = {a['verse']: a for a in data['ayat']}
KUNCI = ('greek_accented', 'greek_stripped', 'kjv', 'ind')

print("=== bandingkan isi teks per ayat ===")
beda = []
for v in env['rag.verse'].search([('chapter','=',8)], order='verse_no'):
    acuan = sumber[v.verse_no]
    for k in KUNCI:
        if (getattr(v, k) or '') != (acuan.get(k) or ''):
            beda.append((v.verse_no, k))
            break
print("ayat berbeda:", beda or "tidak ada")

if beda:
    nomor = sorted({b[0] for b in beda})
    for v in env['rag.verse'].browse([x.id for x in env['rag.verse'].search([('verse_no','in',nomor)])]):
        acuan = sumber[v.verse_no]
        v.write({k: acuan.get(k) for k in KUNCI})
    env.cr.commit()
    print("diperbaiki:", nomor)
    stat = env['rag.chunker'].run(verses=env['rag.verse'].search([('verse_no','in',nomor)]))
    print("chunking ulang:", stat['chunk'])
    chunks = env['rag.chunk'].search([('verse_id.verse_no','in',nomor)])
    st = chunks._embed()
    print("embedding ulang:", st['berhasil'], "berhasil")
    env.cr.commit()

v1 = env['rag.verse'].search([('chapter','=',8),('verse_no','=',1)], limit=1)
print("\nAYT 8:1:", v1.ind)
print("hash cocok dataset:", v1.content_hash == sumber[1]['content_hash'])
print("state:", v1.state, "| chunk:", v1.chunk_ids[:1].state, v1.chunk_ids[:1].dirty)
