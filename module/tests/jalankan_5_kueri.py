import time
Svc = env['rag.query.service']

pertanyaan = [
    "Roma 8:1",
    "Mengapa Paulus berkata tidak ada penghukuman bagi mereka yang di dalam Kristus Yesus?",
    "Apa arti kata κατάκριμα dan bagaimana bentuk gramatikalnya?",
    "Bagaimana perbedaan terjemahan KJV dan AYT pada Roma 8:1?",
    "Jelaskan alur argumen Paulus dari penderitaan menuju kemuliaan",
]

for i, q in enumerate(pertanyaan, 1):
    print(f"\n{'='*70}\n[{i}] {q}")
    t0 = time.time()
    try:
        log = Svc.ask(q)
        env.cr.commit()
        print(f"    rute={log.route_id.code or '-'} | {log.latency_ms} ms | hit={log.hit_count} | "
              f"prompt={log.prompt_tokens} gen={log.completion_tokens}")
        print(f"    tahun: {log.stage_ms}")
        print("    ayat terambil:")
        for h in log.hit_ids:
            print(f"      #{h.position} {h.chunk_id.label:22} dense={h.rank_dense} fts={h.rank_fts} rrf={h.rrf_score:.5f}")
        print("    jawaban:")
        print("      " + (log.answer or '').replace("\n", "\n      ")[:1200])
    except Exception as exc:
        print("    GAGAL:", type(exc).__name__, exc)
    print(f"    (total {time.time()-t0:.1f} detik)")

print("\n=== ringkasan log ===")
for log in env['rag.query.log'].search([], order='id'):
    print(f"  {log.id} {log.route_id.code:6} {log.state:8} {log.latency_ms or 0:6}ms  {log.hit_count} hit  {log.name[:50]}")
