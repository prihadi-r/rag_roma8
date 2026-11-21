import time

lama = env['rag.query.log'].search([])
print("hapus log uji lama:", len(lama))
lama.unlink()
env.cr.commit()

Svc = env['rag.query.service']
pertanyaan = [
    "Roma 8:1",
    "Mengapa Paulus berkata tidak ada penghukuman bagi mereka yang di dalam Kristus Yesus?",
    "Apa arti kata κατάκριμα dan bagaimana bentuk gramatikalnya?",
    "Bagaimana perbedaan terjemahan KJV dan AYT pada Roma 8:1?",
    "Jelaskan alur argumen Paulus dari penderitaan menuju kemuliaan",
]

for i, q in enumerate(pertanyaan, 1):
    print(f"\n{'='*72}\n[{i}] {q}")
    t0 = time.time()
    try:
        log = Svc.ask(q)
        env.cr.commit()
        print(f"    rute={log.route_id.code or '-'} | {log.latency_ms} ms | hit={log.hit_count} | "
              f"prompt={log.prompt_tokens} gen={log.completion_tokens}")
        for h in log.hit_ids:
            print(f"      #{h.position} {h.chunk_id.label:22} dense={h.rank_dense} fts={h.rank_fts} rrf={h.rrf_score:.5f}")
        print("    JAWABAN:")
        print("      " + (log.answer or '').replace("\n", "\n      ")[:1400])
    except Exception as exc:
        print("    GAGAL:", type(exc).__name__, str(exc)[:300])
    print(f"    ({time.time()-t0:.1f} detik)")
