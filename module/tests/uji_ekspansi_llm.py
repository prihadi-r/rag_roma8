import time
Svc = env['rag.query.service']
q = "Bagaimana pandangan Paulus mengenai keselamatan?"
log = env['rag.query.log'].create({'question': q})
env.cr.commit()
print("log id:", log.id)
t0 = time.time()
Svc._jalankan(log)
env.cr.commit()
print("durasi %.1f s | prompt %s gen %s" % (time.time()-t0, log.prompt_tokens, log.completion_tokens))
print("hit:", [(h.chunk_id.label, round(h.rrf_score,5)) for h in log.hit_ids])
print("perluasan di stage:", log.stage_ms.get('expanded'))
print("\n=== JAWABAN ===")
print(log.answer)
a = log.answer or ""
print("\n8:29 disebut?", "8:29" in a, "| 8:30 disebut?", "8:30" in a)
