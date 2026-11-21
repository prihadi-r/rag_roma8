"""Pemformat JSON untuk tampilan form.

Field `Json` di Odoo dirender sebagai satu baris mentah. Fungsi di sini
mengubahnya menjadi teks bertingkat: satu baris untuk satu pasangan
key: value, sehingga bisa dibaca di dalam tab form.
"""
from __future__ import annotations

SPASI = '    '


def _skalar(nilai):
    if nilai is None:
        return '-'
    if isinstance(nilai, bool):
        return 'ya' if nilai else 'tidak'
    if isinstance(nilai, float):
        teks = ('%.6f' % nilai).rstrip('0').rstrip('.')
        return teks or '0'
    return str(nilai)


def format_json(nilai, tingkat: int = 0) -> str:
    """Teks bertingkat: dict → satu baris per kunci, list of dict → blok bernomor."""
    spasi = SPASI * tingkat

    if isinstance(nilai, dict):
        if not nilai:
            return f'{spasi}(kosong)'
        baris = []
        for kunci, isi in nilai.items():
            # nilai kosong tidak ditampilkan agar tidak menenggelamkan data penting
            if isi in (None, '', [], {}):
                continue
            if isinstance(isi, (dict, list)) and isi:
                baris.append(f'{spasi}{kunci}:')
                baris.append(format_json(isi, tingkat + 1))
            else:
                baris.append(f'{spasi}{kunci}: {_skalar(isi)}')
        return '\n'.join(baris) if baris else f'{spasi}(kosong)'

    if isinstance(nilai, list):
        if not nilai:
            return f'{spasi}(kosong)'
        if all(isinstance(x, dict) for x in nilai):
            blok = []
            for urut, item in enumerate(nilai, start=1):
                blok.append(f'{spasi}#{urut}')
                blok.append(format_json(item, tingkat + 1))
            return '\n'.join(blok)
        return f'{spasi}' + ', '.join(_skalar(x) for x in nilai)

    return f'{spasi}{_skalar(nilai)}'
