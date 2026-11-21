print("=== uji akses sebagai RAG User biasa ===")
grp_user = env.ref('rag_teologi.group_rag_user')
grp_mgr = env.ref('rag_teologi.group_rag_manager')
u = env['res.users'].with_context(no_reset_password=True).create({
    'name': 'Uji RAG User', 'login': 'uji_rag_user@example.test',
    'groups_id': [(6, 0, [env.ref('base.group_user').id, grp_user.id])],
})
print("user:", u.login, "| RAG User:", u.has_group('rag_teologi.group_rag_user'),
      "| RAG Manager:", u.has_group('rag_teologi.group_rag_manager'))

wiz = env['rag.query.wizard'].with_user(u).create({'question': 'Roma 8:3'})
print("buat konsol Tanya RAG :", bool(wiz.id))
log = env['rag.query.log'].with_user(u).create({'question': 'Roma 8:3'})
print("buat record kueri    :", log.id, "| state:", log.state, "| pemilik:", log.user_id.login)
print("baca ayat            :", env['rag.verse'].with_user(u).search_count([('chapter','=','8')]), "ayat")
print("baca chunk           :", env['rag.chunk'].with_user(u).search_count([]), "chunk")

try:
    env['rag.config'].with_user(u).write({'rrf_k': 60})
    print("ubah konfigurasi     : TIDAK DITOLAK (masalah!)")
except Exception as exc:
    print("ubah konfigurasi     : ditolak →", type(exc).__name__)
try:
    env['rag.chunking.wizard'].with_user(u).create({})
    print("buka chunking        : TIDAK DITOLAK (masalah!)")
except Exception as exc:
    print("buka chunking        : ditolak →", type(exc).__name__)
env.cr.rollback()
print("(rollback)")
