print("=== 1. buat record kueri baru (seperti klik New) ===")
log = env['rag.query.log'].create({'question': 'Roma 8:2'})
env.cr.commit()
print("   state:", log.state, "| rute:", log.route_id.code or '-', "| hit:", log.hit_count)
print("   jawaban kosong?", not bool(log.answer))

print("\n=== 2. tekan tombol Jalankan Kueri ===")
import time
t0 = time.time()
aksi = log.action_run()
env.cr.commit()
print("   aksi:", aksi.get('tag'), "|", aksi['params']['message'])
print("   durasi total: %.1f detik" % (time.time() - t0))
print("   state:", log.state, "| rute:", log.route_id.code, "| latensi:", log.latency_s)
print("   token:", log.prompt_tokens, "/", log.completion_tokens)
print("   hit:", log.hit_count)
for h in log.hit_ids:
    print("    ", h.position, h.chunk_id.label, "dense=", h.rank_dense, "fts=", h.rank_fts)
print("   JAWABAN:", (log.answer or '')[:400])

print("\n=== 3. jalankan ulang (tidak boleh menggandakan hit) ===")
log.action_run()
env.cr.commit()
print("   hit setelah jalan kedua:", log.hit_count, "| state:", log.state)

print("\n=== 4. record tanpa pertanyaan harus ditolak ===")
kosong = env['rag.query.log'].create({})
try:
    kosong.action_run()
    print("   GAGAL: seharusnya ditolak")
except Exception as exc:
    print("   ditolak:", type(exc).__name__, str(exc)[:80])
env.cr.rollback()
