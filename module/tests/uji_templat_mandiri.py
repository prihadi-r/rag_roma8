cfg = env['rag.config'].get_active()
print("=== konfigurasi tidak lagi punya field templat ===")
print("  'prompt_template_id' pada rag.config:", 'prompt_template_id' in env['rag.config']._fields)

print("\n=== templat berdiri sendiri ===")
w = env['rag.query.wizard'].create({'question': 'uji'})
print("  default wizard:", w.prompt_template_id.name, "v", w.prompt_template_id.version)
tpl_lain = env['rag.prompt.template'].search([('role','=','context_builder')], limit=1)
w.write({'config_id': cfg.id})
print("  setelah pilih konfigurasi:", w.prompt_template_id.name, "v", w.prompt_template_id.version, "(tidak berubah)")
w.write({'prompt_template_id': tpl_lain.id})
print("  ganti templat bebas:", w.prompt_template_id.name)
print("  konfigurasi tetap:", w.config_id.name)

print("\n=== pilihan yang tersedia untuk pengguna ===")
for t in env['rag.prompt.template'].search([('active','=',True)], order='name, version desc'):
    print(f"  - {t.name} v{t.version} ({t.role})")

print("\n=== layanan: templat tersimpan & dipakai ===")
import time
log = env['rag.query.service'].ask('Roma 8:15', cfg, tpl_lain)
env.cr.commit()
print("  log:", log.id, "| config:", log.config_id.name, "| templat:", log.prompt_template_id.name)
print("  params.prompt_template:", (log.params or {}).get('prompt_template'), "v", (log.params or {}).get('prompt_version'))
print("  jawaban:", (log.answer or '')[:120].replace("\n"," "))
