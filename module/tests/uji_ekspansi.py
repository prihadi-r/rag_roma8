Svc = env['rag.query.service']
cfg = env['rag.config'].get_active()
q = "Bagaimana pandangan Paulus mengenai keselamatan?"
tsq, padanan = Svc._tsquery(q)
print("tsquery  :", tsq)
print("padanan  :", padanan)
env.cr.execute("select count(*) from rag_chunk where fts_id @@ to_tsquery('simple', %s)", (tsq,))
print("chunk cocok FTS:", env.cr.fetchone()[0])

print("\n=== RRF top-8 untuk pertanyaan ini ===")
hasil = Svc._cari_hybrid(q, cfg, cfg.embedding_model_id, {})
for i, h in enumerate(hasil[:8], 1):
    tandai = "  ← golden chain" if h['ref'] in ('Roma 8:29', 'Roma 8:30') else ""
    print(f"  {i}. {h['ref']:11} dense={h['rank_dense']} fts={h['rank_fts']} rrf={h['rrf']:.5f}{tandai}")

print("\n=== ayat yang masuk konteks (injected) ===")
inj = [h['ref'] for h in hasil if h['injected']]
print(" ", inj)
print("  8:29 masuk?", 'Roma 8:29' in inj, "| 8:30 masuk?", 'Roma 8:30' in inj)
