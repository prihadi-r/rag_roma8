Svc = env['rag.query.service']
cfg = env['rag.config'].get_active()
model = cfg.embedding_model_id
q = "Bagaimana pandangan Paulus mengenai keselamatan?"

stage = {}
hasil = Svc._cari_hybrid(q, cfg, model, stage)
konteks = Svc._bangun_konteks(hasil, cfg)

print("chunk terambil:", [(h['ref'], round(h['rrf'],5)) for h in hasil])
print("panjang konteks:", len(konteks), "karakter (batas", cfg.context_budget_chars, ")")
print("perkiraan token:", len(konteks)//4)
print()
print("8:29 ada?", "Roma 8:29" in konteks)
print("8:30 ada?", "Roma 8:30" in konteks)
print("perikop yang disertakan:", sorted({h['chunk'].pericope_id.title_id for h in hasil if h['injected']}))
print()
print("=== potongan konteks (8:24 s.d. 8:30) ===")
mulai = konteks.find("Roma 8:24")
print(konteks[mulai-40:mulai+1200])
