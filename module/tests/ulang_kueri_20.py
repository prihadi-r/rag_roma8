import time
Svc = env['rag.query.service']
q = "Bagaimana pandangan Paulus mengenai keselamatan?"
log = env['rag.query.log'].create({'question': q})
env.cr.commit()
print("log baru id:", log.id)
t0 = time.time()
Svc._jalankan(log)
env.cr.commit()
print("durasi %.1f s | rute %s | prompt %s gen %s" % (
    time.time()-t0, log.route_id.code, log.prompt_tokens, log.completion_tokens))
print("hit:", [(h.chunk_id.label, round(h.rrf_score,5)) for h in log.hit_ids])
print("\n=== JAWABAN ===")
print(log.answer)
