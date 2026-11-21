import time
cfg_default = env['rag.config'].get_active()
print("konfigurasi default:", cfg_default.name)

# preset kedua
cepat = env['rag.config'].create({
    'name': 'Uji Cepat (maks 200 token)',
    'sequence': 20,
    'embedding_model_id': cfg_default.embedding_model_id.id,
    'chat_base_url': cfg_default.chat_base_url,
    'chat_model': cfg_default.chat_model,
    'embed_base_url': cfg_default.embed_base_url,
    'prompt_template_id': cfg_default.prompt_template_id.id,
    'max_tokens': 200,
    'temperature': 0.1,
})
env.cr.commit()
print("preset kedua:", cepat.name, "| aktif:", cepat.active)

print("\n=== 1. pengaman: konfigurasi dengan model embedding berbeda ===")
lain = env['rag.embedding.model'].create({'name': 'uji-e5-768', 'dimensions': 768, 'endpoint': 'http://127.0.0.1:9/x'})
salah = env['rag.config'].create({'name': 'Uji Salah Model', 'sequence': 30,
                                  'embedding_model_id': lain.id})
try:
    env['rag.query.service'].ask('Roma 8:1', config=salah)
    print("   TIDAK DITOLAK (masalah)")
except Exception as exc:
    print("   ditolak:", type(exc).__name__, "→", str(exc)[:150])

print("\n=== 2. jalankan kueri memakai preset kedua ===")
wiz = env['rag.query.wizard'].create({
    'question': 'Roma 8:15',
    'config_id': cepat.id,
})
t0 = time.time()
aksi = wiz.action_ask()
print("   durasi %.1f s" % (time.time() - t0))
print("   info:", wiz.info)
log = wiz.log_id
print("   konfigurasi tercatat:", log.config_id.name)
print("   token jawaban:", log.completion_tokens, "(batas preset 200)")
print("   jawaban:", (log.answer or '')[:200])

env.cr.commit()
print("\n=== 3. default tetap konfigurasi urutan terkecil ===")
print("   get_active():", env['rag.config'].get_active().name)
print("   jumlah konfigurasi aktif:", env['rag.config'].search_count([('active','=',True)]))
