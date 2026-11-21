grp_user = env.ref('rag_teologi.group_rag_user')
u = env['res.users'].with_context(no_reset_password=True).create({
    'name': 'Uji RAG User 2', 'login': 'uji_rag_user2@example.test',
    'groups_id': [(6, 0, [env.ref('base.group_user').id, grp_user.id])],
})
cfg = env['rag.config'].search([], limit=1)
verse = env['rag.verse'].search([], limit=1)
varian = env['rag.variant'].search([], limit=1)

uji = [
    ("ubah konfigurasi", lambda: cfg.with_user(u).write({'rrf_k': 61})),
    ("ubah ayat",        lambda: verse.with_user(u).write({'ind': 'x'})),
    ("hapus varian",     lambda: varian.with_user(u).unlink()),
    ("buka chunking",    lambda: env['rag.chunking.wizard'].with_user(u).create({})),
    ("impor dataset",    lambda: env['rag.import.wizard'].with_user(u).create({})),
]
for nama, fn in uji:
    try:
        with env.cr.savepoint():
            fn()
        print(f"  {nama:20}: TIDAK DITOLAK (masalah)")
    except Exception as exc:
        print(f"  {nama:20}: ditolak → {type(exc).__name__}")

print()
print("=== yang seharusnya boleh ===")
ok = [
    ("baca ayat",   lambda: env['rag.verse'].with_user(u).search_count([])),
    ("baca chunk",  lambda: env['rag.chunk'].with_user(u).search_count([])),
    ("buka konsol", lambda: env['rag.query.wizard'].with_user(u).create({'question': 'x'})),
    ("buat kueri",  lambda: env['rag.query.log'].with_user(u).create({'question': 'x'})),
]
for nama, fn in ok:
    try:
        print(f"  {nama:12}: ok → {fn() if isinstance(fn(), int) else 'dibuat'}")
    except Exception as exc:
        print(f"  {nama:12}: GAGAL → {type(exc).__name__}")
env.cr.rollback()
