from odoo import api, fields, models
from odoo.exceptions import ValidationError


class RagEmbeddingModel(models.Model):
    _name = 'rag.embedding.model'
    _table = 'rag_embedding_model'
    _description = 'Model Embedding'

    name = fields.Char(string='Nama', required=True, help='Contoh: bge-m3-Q8_0')
    provider = fields.Char(string='Penyedia', default='llamacpp')
    api_model = fields.Char(string='Nama Model di API', default='bge-m3',
                            help='Nilai "model" yang dikirim ke /v1/embeddings; harus sama dengan --alias llama-server.')
    endpoint = fields.Char(string='Endpoint', default='http://127.0.0.1:8080/v1/embeddings')
    dimensions = fields.Integer(string='Dimensi', required=True, default=1024)
    quantization = fields.Char(string='Kuantisasi', default='Q8_0')
    normalized = fields.Boolean(string='Sudah Ternormalisasi', default=True)
    active = fields.Boolean(default=True)

    _name_uniq = models.Constraint('unique(name)', 'Nama model harus unik.')

    _dim_positive = models.Constraint('check(dimensions > 0)', 'Dimensi harus positif.')


class RagPromptTemplate(models.Model):
    _name = 'rag.prompt.template'
    _table = 'rag_prompt_template'
    _description = 'Templat Prompt (berversi)'
    _order = 'name, version desc'

    name = fields.Char(string='Nama', required=True)
    role = fields.Char(string='Peran', default='system', help='system / context_builder')
    body = fields.Text(string='Isi', help='Placeholder yang tersedia: {{context}}, {{variants}}')
    version = fields.Integer(string='Versi', default=1)
    active = fields.Boolean(default=True)

    _name_version_uniq = models.Constraint('unique(name, version)', 'Nama+versi templat harus unik.')


class RagConfig(models.Model):
    _name = 'rag.config'
    _table = 'rag_config'
    _description = 'Konfigurasi LLM & RAG'

    name = fields.Char(string='Nama', required=True, default='Roma 8 — lokal')
    sequence = fields.Integer(string='Urutan', default=10,
                              help='Konfigurasi aktif dengan urutan terkecil dipakai sebagai default.')
    chat_base_url = fields.Char(string='URL Chat', default='http://127.0.0.1:8081/v1')
    chat_model = fields.Char(string='Model Chat', default='qwen2.5-7b-instruct')
    embed_base_url = fields.Char(string='URL Embedding', default='http://127.0.0.1:8080/v1')
    embedding_model_id = fields.Many2one('rag.embedding.model', string='Model Embedding', required=True, ondelete='restrict')

    top_k_dense = fields.Integer(string='Kandidat Vektor', default=20)
    top_k_fts = fields.Integer(string='Kandidat Full-text', default=20)
    rrf_k = fields.Integer(string='Konstanta RRF', default=60)
    top_k_final = fields.Integer(string='Masuk Konteks', default=5)

    temperature = fields.Float(string='Temperature', default=0.2)
    max_tokens = fields.Integer(string='Maks Token Jawaban', default=600)
    context_budget_chars = fields.Integer(string='Anggaran Konteks (karakter)', default=6000)
    timeout_chat_s = fields.Integer(string='Timeout Chat (detik)', default=180)
    timeout_embed_s = fields.Integer(string='Timeout Embedding (detik)', default=30)

    active = fields.Boolean(default=True)

    @api.constrains('temperature')
    def _check_temperature(self):
        for rec in self:
            if not 0.0 <= rec.temperature <= 2.0:
                raise ValidationError('Temperature harus antara 0 dan 2.')

    @api.model
    def get_active(self):
        """Konfigurasi default: aktif dengan urutan terkecil.

        Beberapa konfigurasi boleh aktif sekaligus sebagai preset yang bisa
        dipilih per kueri; yang ini hanya default bila pengguna tidak memilih.
        """
        return self.search([('active', '=', True)], order='sequence, id', limit=1)
