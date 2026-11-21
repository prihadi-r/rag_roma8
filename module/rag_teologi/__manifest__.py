{
    'name': 'RAG Teologi — Roma 8',
    'version': '18.2.1.0.0',
    'summary': 'Mesin RAG lokal untuk eksposisi dan perbandingan tekstual Roma 8',
    'description': """
RAG Teologi
===========

Mesin Retrieval-Augmented Generation yang berdiri sendiri di dalam Odoo,
tanpa orchestrator eksternal.

Sumber paralel per ayat:
  * Yunani Koine — Robinson-Pierpont 2018 (Byzantine Textform), public domain
  * Inggris     — King James Version 1769, public domain
  * Indonesia   — AYT (Alkitab Yang Terbuka), CC, non-komersial

Arsitektur:
  * PostgreSQL + pgvector (HNSW) + tsvector (GIN) + pg_trgm
  * Dua instance llama.cpp (chat & embedding), API kompatibel OpenAI
  * Hybrid search dengan Reciprocal Rank Fusion (RRF)
  * Varian tekstual disimpan sebagai data apparatus, bukan disimpulkan LLM
    """,
    'author': 'Proyek RAG Roma 8',
    'category': 'Productivity',
    'license': 'LGPL-3',
    'depends': ['base'],
    'data': [
        'security/rag_security.xml',
        'security/ir.model.access.csv',
        'data/rag_master_data.xml',
        'data/rag_cron.xml',
        'data/rag_expansion_data.xml',
        'views/rag_data_views.xml',
        'views/rag_config_views.xml',
        'views/rag_query_views.xml',
        'views/rag_import_wizard_views.xml',
        'views/rag_chunking_wizard_views.xml',
        'views/rag_query_wizard_views.xml',
        'views/rag_expansion_views.xml',
        'views/rag_menu.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': True,
}
