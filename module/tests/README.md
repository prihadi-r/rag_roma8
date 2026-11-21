# Skrip uji & diagnostik

Berkas di sini adalah **skrip operasional dan diagnostik** yang dijalankan lewat
`odoo-bin shell`, bukan unit test otomatis. Sebagian besar lahir saat menelusuri
masalah tertentu dan disimpan sebagai bukti/reproduksi.

Menjalankan:

```bash
python3 scripts/rrun.py --put module/tests/test_rag_module.py /tmp/t.py
python3 scripts/rrun.py --sudo 'cd /opt/odoo18 && \
  sudo -u odoo18 /opt/odoo18/venv/bin/python3 /opt/odoo18/odoo-bin shell \
  -c /etc/odoo18.conf -d rag_roma8 --no-http < /tmp/t.py'
```

| Berkas | Kegunaan |
|---|---|
| `test_rag_module.py` | uji fungsional modul (model, vektor, FTS, constraint) — semua di-*rollback* |
| `jalankan_impor.py` | impor dataset 39 ayat lewat wizard |
| `jalankan_chunking.py` | chunking + inspeksi `embed_text` |
| `jalankan_embedding.py` | isi vektor lewat `_cron_embed` |
| `jalankan_5_kueri2.py` | lima kueri uji end-to-end |
| `uji_pencarian.py` | uji kualitas pencarian semantik |
| `uji_ekspansi.py`, `uji_ekspansi_llm.py` | dampak ekspansi kueri |
| `uji_tombol_kueri.py`, `uji_tombol_reembed.py` | tombol eksekusi & re-embed |
| `uji_akses_user2.py` | batas hak akses RAG User |
| `uji_pilih_config.py` | pilihan Pengaturan RAG per kueri + pengaman model |
| `perbaiki_data2.py` | bandingkan teks DB dengan dataset, perbaiki yang menyimpang |
| `diagnosa_*.py`, `debug*.py` | penelusuran masalah (disimpan sebagai jejak) |

Semua skrip yang mengubah data melakukan `commit()` **kecuali** yang eksplisit
menyebut rollback. Periksa sebelum menjalankan pada database berisi data nyata.
