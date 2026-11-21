from odoo.addons.rag_teologi.models.embedding_client import embed_texts

cfg = env['rag.config'].get_active()
model = cfg.embedding_model_id
endpoint = model.endpoint

def cari(kueri, k=3):
    vec = embed_texts(endpoint, model.api_model or model.name, [kueri], timeout=30)[0]
    lit = '[' + ','.join('%.7g' % float(x) for x in vec) + ']'
    env.cr.execute("""
        SELECT c.verse_id, v.ref_label,
               round((1 - (c.embedding <=> %s::vector))::numeric, 4) AS cos
        FROM rag_chunk c JOIN rag_verse v ON v.id = c.verse_id
        ORDER BY c.embedding <=> %s::vector LIMIT %s
    """, (lit, lit, k))
    return env.cr.fetchall()

uji = [
    ("tidak ada penghukuman bagi yang di dalam Kristus", [1]),
    ("pengangkatan menjadi anak Allah", [15, 23]),
    ("kemuliaan yang akan dinyatakan kelak", [18, 30]),
    ("Roh menolong kelemahan kita", [26]),
    ("tidak ada yang dapat memisahkan kita dari kasih Allah", [35, 38, 39]),
    ("hidup menurut daging vs menurut Roh", [5, 6, 8]),
]
print("=== PENCARIAN SEMANTIK (cosine) ===")
benar = 0
for kueri, harus in uji:
    hasil = cari(kueri, 3)
    label = [h[1] for h in hasil]
    kena = any(int(h[1].split(':')[1]) in harus for h in hasil)
    benar += kena
    print(f"\n'{kueri}'  →  target {harus}  {'✅' if kena else '❌'}")
    for vid, ref, cos in hasil:
        print(f"   {cos:.4f}  {ref}")
print(f"\nTepat sasaran: {benar}/{len(uji)}")

print("\n=== RENCANA EKSEKUSI HNSW ===")
env.cr.execute("SET enable_seqscan = off")
env.cr.execute("EXPLAIN SELECT id FROM rag_chunk ORDER BY embedding <=> (SELECT embedding FROM rag_chunk LIMIT 1) LIMIT 3")
for baris in env.cr.fetchall():
    print("  ", baris[0])
