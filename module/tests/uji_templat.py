import time
Tpl = env['rag.prompt.template']
ringkas = Tpl.search([('name','=','ringkas-dua-kalimat'),('version','=',1)], limit=1)
if not ringkas:
    ringkas = Tpl.create({
        'name': 'ringkas-dua-kalimat', 'role': 'system', 'version': 1, 'active': True,
        'body': ("Jawab HANYA berdasarkan KONTEKS. Maksimal DUA kalimat. "
                 "Sebutkan nomor ayat pada setiap kalimat. Tanpa pengantar, tanpa kesimpulan tambahan."),
    })
cfg = env['rag.config'].get_active()
print("templat uji:", ringkas.name, "v", ringkas.version)
print("templat dari konfigurasi:", cfg.prompt_template_id.name)

print("\n=== wizard: templat otomatis mengikuti konfigurasi ===")
w = env['rag.query.wizard'].create({'question': 'uji', 'config_id': cfg.id})
print("  compute:", w.prompt_template_id.name)

print("\n=== jalankan kueri memakai templat ringkas ===")
t0 = time.time()
log = env['rag.query.service'].ask('Roma 8:1', cfg, ringkas)
env.cr.commit()
print("  durasi %.1f s" % (time.time() - t0))
print("  log id:", log.id)
print("  pengaturan RAG:", log.config_id.name)
print("  templat tercatat:", log.prompt_template_id.name, "v", log.prompt_template_id.version)
print("  params.prompt_template:", (log.params or {}).get('prompt_template'), "v", (log.params or {}).get('prompt_version'))
print("  token jawaban:", log.completion_tokens)
print("  JAWABAN:", (log.answer or '').strip()[:400])
print("  jumlah kalimat:", (log.answer or '').count('.'))

print("\n=== riwayat 27 (kueri lama) ===")
lama = env['rag.query.log'].browse(27)
print("  pengaturan RAG:", lama.config_id.name if lama.config_id else '-')
print("  templat:", lama.prompt_template_id.name if lama.prompt_template_id else '-')
