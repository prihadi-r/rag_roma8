import time
Tpl = env['rag.prompt.template']
lama = Tpl.search([('name','=','eksposisi-grounding'),('version','=',1)], limit=1)
baru = Tpl.search([('name','=','eksposisi-grounding'),('version','=',2)], limit=1)
isi = """Anda adalah asisten eksegesis Alkitab yang ketat.

ATURAN:
1. Jawab HANYA berdasarkan KONTEKS yang diberikan. Jangan menambahkan ayat lain.
2. Setiap klaim harus menyebut nomor ayat dan mengutip kata persis dari konteks.
3. Ayat bertanda ▶ adalah hasil pencarian. Ayat lain dalam perikop yang sama adalah KONTEKS.
   TELUSURI SELURUH PERIKOP yang diberikan, bukan hanya ayat bertanda ▶ — terutama bila
   pertanyaan menyangkut doktrin, keselamatan, atau alur argumen Paulus.
4. Bila ada blok [VARIAN TEKSTUAL], bandingkan KEHADIRAN klausa antar saksi — bukan hanya
   pilihan kata.
5. Jika konteks tidak memuat jawabannya, katakan demikian. Jangan mengarang.
6. Bahasa: Indonesia. Istilah Yunani ditulis dalam huruf Yunani bila tersedia."""
if not baru:
    baru = Tpl.create({'name': 'eksposisi-grounding', 'role': 'system', 'version': 2, 'body': isi})
else:
    baru.write({'body': isi})
cfg = env['rag.config'].get_active()
cfg.write({'prompt_template_id': baru.id})
env.cr.commit()
print("templat v2 dibuat, konfigurasi diarahkan ke v2")

Svc = env['rag.query.service']
q = "Bagaimana pandangan Paulus mengenai keselamatan?"
log = env['rag.query.log'].create({'question': q})
env.cr.commit()
print("log id:", log.id)
t0 = time.time()
Svc._jalankan(log)
env.cr.commit()
print("durasi %.1f s | prompt %s gen %s" % (time.time()-t0, log.prompt_tokens, log.completion_tokens))
print("\n=== JAWABAN (templat v2) ===")
print(log.answer)
print("\n8:29 disebut?", "8:29" in (log.answer or ""))
print("8:30 disebut?", "8:30" in (log.answer or ""))
