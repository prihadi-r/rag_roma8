"""Klien HTTP ke endpoint /v1/embeddings milik llama.cpp.

Dipisahkan dari model agar bisa diuji tanpa Odoo. Memakai `requests` yang
sudah tersedia di venv Odoo.
"""
import logging
import time

import requests

_logger = logging.getLogger(__name__)


class EmbeddingError(Exception):
    """Kegagalan yang layak ditampilkan ke pengguna."""


def embed_texts(endpoint, api_model, texts, timeout=30, retries=3, backoff=1.5):
    """Kembalikan daftar vektor untuk `texts`, sesuai urutan input.

    Mencoba ulang pada kegagalan jaringan/5xx; tidak mengulang pada 4xx
    (permintaan salah, mengulang tidak akan menolong).
    """
    if not texts:
        return []

    payload = {'model': api_model, 'input': texts}
    percobaan_terakhir = None

    for percobaan in range(1, retries + 1):
        try:
            resp = requests.post(
                endpoint,
                json=payload,
                timeout=timeout,
                headers={'Content-Type': 'application/json'},
            )
            if 400 <= resp.status_code < 500:
                raise EmbeddingError(
                    "Endpoint embedding menolak permintaan (HTTP %s): %s"
                    % (resp.status_code, resp.text[:300])
                )
            resp.raise_for_status()
            data = resp.json()
            butir = data.get('data') or []
            if len(butir) != len(texts):
                raise EmbeddingError(
                    "Jumlah vektor tidak cocok: diminta %d, diterima %d"
                    % (len(texts), len(butir))
                )
            butir.sort(key=lambda d: d.get('index', 0))
            return [d['embedding'] for d in butir]
        except EmbeddingError:
            raise
        except Exception as exc:  # noqa: BLE001
            percobaan_terakhir = exc
            _logger.warning(
                "Embedding gagal (percobaan %d/%d): %s", percobaan, retries, exc)
            if percobaan < retries:
                time.sleep(backoff ** percobaan)

    raise EmbeddingError(
        "Endpoint embedding tidak dapat dihubungi setelah %d percobaan: %s"
        % (retries, percobaan_terakhir)
    )


def cek_kesehatan(endpoint, timeout=5):
    """True bila endpoint merespons."""
    dasar = endpoint.rsplit('/v1/', 1)[0]
    try:
        resp = requests.get(dasar + '/health', timeout=timeout)
        return resp.status_code == 200
    except Exception:  # noqa: BLE001
        return False
