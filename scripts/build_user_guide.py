#!/usr/bin/env python3
"""Bangun USER_GUIDE.docx dari docs/img/*.png.

    python3 scripts/build_user_guide.py

Menghasilkan USER_GUIDE.docx di akar repositori.
"""
from __future__ import annotations

from pathlib import Path

import io

from PIL import Image, ImageChops
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parent.parent
IMG = ROOT / "docs" / "img"
OUT = ROOT / "USER_GUIDE.docx"

AKSEN = RGBColor(0x5B, 0x3F, 0x8F)
ABU = RGBColor(0x60, 0x60, 0x60)

gambar_ke = 0
tabel_ke = 0


# --------------------------------------------------------------------- util
def set_cell_bg(cell, warna_hex):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:fill'), warna_hex)
    tcPr.append(shd)


def tambah_nomor_halaman(paragraf):
    run = paragraf.add_run()
    for tag, teks in (('begin', None), (None, 'PAGE'), ('end', None)):
        if tag:
            fld = OxmlElement('w:fldChar')
            fld.set(qn('w:fldCharType'), tag)
            run._r.append(fld)
        else:
            instr = OxmlElement('w:instrText')
            instr.set(qn('xml:space'), 'preserve')
            instr.text = teks
            run._r.append(instr)


def potong_putih(path, pad=10):
    """Potong tepi yang seragam putih agar gambar tidak menyisakan ruang kosong."""
    im = Image.open(path).convert('RGB')
    latar = Image.new('RGB', im.size, (255, 255, 255))
    kotak = ImageChops.difference(im, latar).getbbox()
    if not kotak:
        return im
    kiri = max(0, kotak[0] - pad)
    atas = max(0, kotak[1] - pad)
    kanan = min(im.width, kotak[2] + pad)
    bawah = min(im.height, kotak[3] + pad)
    return im.crop((kiri, atas, kanan, bawah))


def gambar(doc, nama, caption, lebar_cm=16.2):
    global gambar_ke
    path = IMG / nama
    if not path.exists():
        raise SystemExit(f"gambar tidak ditemukan: {path}")
    potongan = potong_putih(path)
    bufer = io.BytesIO()
    potongan.save(bufer, format='PNG')
    bufer.seek(0)
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    par.paragraph_format.space_before = Pt(6)
    par.paragraph_format.keep_with_next = True
    par.add_run().add_picture(bufer, width=Cm(lebar_cm))
    gambar_ke += 1
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.paragraph_format.space_after = Pt(12)
    cap.paragraph_format.keep_together = True
    run = cap.add_run(f"Gambar {gambar_ke} — {caption}")
    run.italic = True
    run.font.size = Pt(8.5)
    run.font.color.rgb = ABU


def tabel(doc, judul, kolom, baris, lebar=None):
    global tabel_ke
    tabel_ke += 1
    cap = doc.add_paragraph()
    run = cap.add_run(f"Tabel {tabel_ke} — {judul}")
    run.italic = True
    run.font.size = Pt(8.5)
    run.font.color.rgb = ABU
    cap.paragraph_format.space_before = Pt(8)

    t = doc.add_table(rows=1, cols=len(kolom))
    t.style = 'Table Grid'
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr = t.rows[0].cells
    for i, teks in enumerate(kolom):
        hdr[i].text = ''
        p = hdr[i].paragraphs[0]
        r = p.add_run(teks)
        r.bold = True
        r.font.size = Pt(9)
        set_cell_bg(hdr[i], 'EDE7F6')
    for isi in baris:
        sel = t.add_row().cells
        for i, teks in enumerate(isi):
            sel[i].text = ''
            p = sel[i].paragraphs[0]
            r = p.add_run(str(teks))
            r.font.size = Pt(9)
    for row in t.rows:
        trPr = row._tr.get_or_add_trPr()
        cant = OxmlElement('w:cantSplit')
        trPr.append(cant)
    if lebar:
        for row in t.rows:
            for i, w in enumerate(lebar):
                row.cells[i].width = Cm(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(4)
    return t


def catatan(doc, judul, isi):
    par = doc.add_paragraph()
    par.paragraph_format.left_indent = Cm(0.4)
    par.paragraph_format.space_before = Pt(6)
    par.paragraph_format.space_after = Pt(10)
    r = par.add_run(f"{judul} ")
    r.bold = True
    r.font.color.rgb = AKSEN
    par.add_run(isi)


def langkah(doc, items):
    """Daftar bernomor manual — gaya List Number melanjutkan nomor antar bagian."""
    for i, teks in enumerate(items, start=1):
        par = doc.add_paragraph()
        par.paragraph_format.left_indent = Cm(0.75)
        par.paragraph_format.first_line_indent = Cm(-0.75)
        par.paragraph_format.space_after = Pt(3)
        r = par.add_run(f"{i}.  ")
        r.bold = True
        par.add_run(teks)


def butir(doc, items):
    for teks in items:
        par = doc.add_paragraph(style='List Bullet')
        par.paragraph_format.space_after = Pt(3)
        par.add_run(teks)


def kode(par, teks):
    run = par.add_run(teks)
    run.font.name = 'Consolas'
    run.font.size = Pt(9)
    run._element.rPr.rFonts.set(qn('w:eastAsia'), 'Consolas')
    return run


# -------------------------------------------------------------------- dokumen
def main() -> int:
    doc = Document()

    gaya = doc.styles['Normal']
    gaya.font.name = 'Calibri'
    gaya.font.size = Pt(10.5)
    gaya.paragraph_format.space_after = Pt(6)
    gaya.paragraph_format.line_spacing = 1.15

    for nama, ukuran in (('Heading 1', 16), ('Heading 2', 12.5), ('Heading 3', 11)):
        st = doc.styles[nama]
        st.font.name = 'Calibri'
        st.font.size = Pt(ukuran)
        st.font.color.rgb = AKSEN
        st.font.bold = True
        st.paragraph_format.keep_with_next = True

    sec = doc.sections[0]
    sec.page_width = Cm(21)
    sec.page_height = Cm(29.7)
    sec.top_margin = Cm(2.2)
    sec.bottom_margin = Cm(2.0)
    sec.left_margin = Cm(2.3)
    sec.right_margin = Cm(2.3)

    kaki = sec.footer.paragraphs[0]
    kaki.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = kaki.add_run('Panduan Pengguna RAG Teologi Roma 8  ·  halaman ')
    r.font.size = Pt(8)
    r.font.color.rgb = ABU
    tambah_nomor_halaman(kaki)

    # ------------------------------------------------------------- sampul
    for _ in range(3):
        doc.add_paragraph()
    judul = doc.add_paragraph()
    judul.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = judul.add_run('Panduan Pengguna')
    r.font.size = Pt(34)
    r.bold = True
    r.font.color.rgb = AKSEN

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = sub.add_run('RAG Teologi — Roma 8:1–39')
    r.font.size = Pt(20)
    r.font.color.rgb = ABU

    doc.add_paragraph()
    ket = doc.add_paragraph()
    ket.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = ket.add_run('Modul Odoo untuk studi eksposisi dan perbandingan tekstual\n'
                    'Yunani Koine · KJV · AYT')
    r.font.size = Pt(11)
    r.italic = True

    for _ in range(6):
        doc.add_paragraph()

    info = doc.add_table(rows=0, cols=2)
    info.alignment = WD_TABLE_ALIGNMENT.CENTER
    for label, nilai in [
        ('Versi dokumen', '1.0'),
        ('Tanggal', '21 November 2026'),
        ('Aplikasi', 'Odoo 18.2 · modul rag_teologi'),
        ('Alamat', 'http://192.168.18.222:8069'),
        ('Database', 'rag_roma8'),
        ('Lisensi data', 'Robinson-Pierpont & KJV: public domain · AYT: non-komersial'),
    ]:
        sel = info.add_row().cells
        sel[0].width = Cm(4.5)
        sel[1].width = Cm(9.5)
        p0 = sel[0].paragraphs[0]
        r0 = p0.add_run(label)
        r0.bold = True
        r0.font.size = Pt(9.5)
        p1 = sel[1].paragraphs[0]
        r1 = p1.add_run(nilai)
        r1.font.size = Pt(9.5)

    doc.add_page_break()

    # --------------------------------------------------------------- isi
    doc.add_heading('Isi dokumen', level=1)
    daftar = [
        '1. Tentang aplikasi ini',
        '2. Masuk dan mengenal antarmuka',
        '3. Melihat data ayat, perikop, dan varian',
        '4. Mengajukan pertanyaan (konsol Tanya RAG)',
        '5. Membaca jawaban dan riwayat kueri',
        '6. Menjalankan kueri dari Riwayat Kueri',
        '7. Memilih Pengaturan RAG per kueri',
        '8. Pengelolaan data (RAG Manager)',
        '9. Alur kerja yang disarankan',
        '10. Pemecahan masalah',
        '11. Batasan dan tips kualitas',
        '12. Lampiran: sumber data, lisensi, dan istilah',
    ]
    for teks in daftar:
        par = doc.add_paragraph(teks)
        par.paragraph_format.space_after = Pt(2)

    doc.add_paragraph()
    catatan(
        doc, 'Catatan:',
        'Panduan ini memakai tangkapan layar sungguhan dari aplikasi. Data yang tampak '
        '(ayat, varian, kueri) adalah data nyata Roma 8:1–39 yang sudah diimpor.')

    # ------------------------------------------------------------ Bagian 1
    doc.add_page_break()
    doc.add_heading('1. Tentang aplikasi ini', level=1)
    doc.add_paragraph(
        'RAG Teologi adalah mesin tanya-jawab Alkitab yang berjalan di dalam Odoo. Ia '
        'mengambil ayat dari korpus Roma 8:1–39, menyusun konteks dari ayat dan perikopnya, '
        'lalu meminta model bahasa lokal menjawab berdasarkan konteks itu saja.')
    doc.add_paragraph(
        'Setiap ayat disandingkan dalam tiga bahasa sekaligus: Yunani Koine '
        '(Robinson-Pierpont 2018), Inggris (KJV 1769), dan Indonesia (AYT). Perbedaan teks '
        'antar tradisi — misalnya klausa Roma 8:1 yang ada pada tradisi Byzantine tetapi '
        'dihilangkan Nestle-Aland — disimpan sebagai data dan ditampilkan apa adanya, bukan '
        'disimpulkan oleh model.')

    doc.add_heading('Siapa boleh melakukan apa', level=2)
    tabel(doc, 'Peran pengguna', ['Peran', 'Boleh melakukan', 'Tidak boleh'], [
        ['RAG User', 'Mengajukan pertanyaan, melihat riwayat kuerinya sendiri',
         'Mengubah ayat, konfigurasi, atau menjalankan impor'],
        ['RAG Manager', 'Semua di atas, ditambah impor data, chunking, embedding, '
                        'dan mengubah konfigurasi',
         '—'],
    ], lebar=[3.2, 8.6, 4.8])
    catatan(doc, 'Penting:',
            'Bila Anda tidak melihat menu Konfigurasi, akun Anda hanya memiliki peran '
            'RAG User. Hubungi administrator untuk penambahan hak.')

    # ------------------------------------------------------------ Bagian 2
    doc.add_heading('2. Masuk dan mengenal antarmuka', level=1)
    doc.add_heading('2.1 Masuk', level=2)
    doc.add_paragraph(
        'Buka peramban dan arahkan ke alamat aplikasi. Karena server menampung beberapa '
        'database Odoo, pastikan database yang dipilih adalah rag_roma8.')
    langkah(doc, [
        'Buka http://192.168.18.222:8069/web/login?db=rag_roma8',
        'Masukkan surel dan kata sandi akun Anda.',
        'Klik Masuk. Halaman awal Odoo akan terbuka.',
    ])
    catatan(doc, 'Lupa kata sandi:',
            'Hubungi administrator. Kata sandi tidak dapat dipulihkan dari aplikasi; '
            'administrator akan mengatur ulang melalui server.')

    doc.add_heading('2.2 Menu utama', level=2)
    doc.add_paragraph(
        'Seluruh fitur berada di bilah atas dengan tiga kelompok menu: Data, Kueri, dan '
        'Konfigurasi.')
    gambar(doc, '01-menu.png', 'Menu Data pada modul RAG Teologi.')
    tabel(doc, 'Struktur menu', ['Menu', 'Isi', 'Untuk siapa'], [
        ['Data', 'Kitab, Perikop, Ayat, Chunk, Varian Tekstual', 'Semua pengguna (baca)'],
        ['Kueri → Tanya RAG', 'Konsol mengajukan pertanyaan', 'Semua pengguna'],
        ['Kueri → Riwayat Kueri', 'Daftar pertanyaan, jawaban, dan audit', 'Semua pengguna'],
        ['Konfigurasi', 'Pengaturan RAG, Model Embedding, Templat Prompt, Ekspansi Kueri, '
                        'Batch Impor, Impor Dataset, Jalankan Chunking', 'RAG Manager'],
    ], lebar=[3.6, 8.4, 4.6])

    # ------------------------------------------------------------ Bagian 3
    doc.add_heading('3. Melihat data ayat, perikop, dan varian', level=1)
    doc.add_heading('3.1 Daftar ayat', level=2)
    doc.add_paragraph(
        'Menu Data → Ayat menampilkan 39 ayat Roma 8. Kolomnya menunjukkan mutu data: '
        'berapa kata Yunani, berapa varian tekstual, dan apakah ayat sudah ter-embed.')
    gambar(doc, '02-daftar-ayat.png', 'Daftar ayat beserta perikop, jumlah kata, varian, dan status.')
    tabel(doc, 'Arti kolom pada daftar ayat', ['Kolom', 'Arti'], [
        ['Referensi', 'Label ayat, mis. Roma 8:29'],
        ['Perikop', 'Perikop induk — unit konteks yang dipakai saat menjawab'],
        ['Jumlah Kata', 'Jumlah kata Yunani hasil parsing (bukan jumlah kata terjemahan)'],
        ['Jumlah Varian', 'Banyak varian tekstual pada ayat itu'],
        ['Status', 'Draf → Ter-chunk → Ter-embed. Hanya ayat Ter-embed yang ikut pencarian'],
        ['Perlu Diproses', 'Penanda kotor: teks berubah dan menunggu di-embed ulang'],
    ], lebar=[3.8, 12.4])

    doc.add_heading('3.2 Form ayat', level=2)
    doc.add_paragraph(
        'Klik satu baris untuk membuka form ayat. Semua teks tersimpan di sini: Yunani '
        'berdiakritik, Yunani tanpa aksen, transliterasi, KJV, Indonesia, morfologi per kata, '
        'dan varian.')
    gambar(doc, '03-form-ayat.png', 'Form ayat Roma 8:29 — tab Yunani.')
    tabel(doc, 'Tab pada form ayat', ['Tab', 'Isi'], [
        ['Yunani', 'Teks berdiakritik, bentuk tanpa aksen, dan transliterasi Latin'],
        ['KJV', 'Terjemahan 1769; kata sisipan penerjemah tetap ditandai'],
        ['Indonesia', 'Teks AYT beserta keterangan sumbernya'],
        ['Morfologi', 'Daftar kata: nomor Strong dan kode parsing Robinson'],
        ['Varian', 'Varian tekstual ayat ini beserta saksi dan jenisnya'],
        ['Chunk', 'Unit pencarian yang dibentuk dari ayat ini'],
    ], lebar=[3.4, 12.8])

    doc.add_heading('3.3 Varian tekstual', level=2)
    doc.add_paragraph(
        'Menu Data → Varian Tekstual memperlihatkan perbedaan bacaan antar tradisi. '
        'Contohnya Roma 8:1: tradisi Byzantine memuat klausa "jangan hidup menurut daging, '
        'tetapi menurut Roh", sedangkan Nestle-Aland menghilangkannya. Data inilah yang '
        'disodorkan ke model agar perbedaan tersebut tidak dikarang.')
    gambar(doc, '04-varian.png', 'Daftar varian tekstual: saksi, jenis, dan bacaan.')

    # ------------------------------------------------------------ Bagian 4
    doc.add_heading('4. Mengajukan pertanyaan (konsol Tanya RAG)', level=1)
    doc.add_paragraph(
        'Ini cara utama memakai aplikasi. Satu pertanyaan akan dicarikan ayat yang relevan, '
        'lalu dijawab oleh model bahasa berdasarkan ayat-ayat itu.')
    langkah(doc, [
        'Buka Kueri → Tanya RAG.',
        'Tulis pertanyaan pada kotak paling atas.',
        'Bila perlu, pilih Pengaturan RAG dan Templat Prompt tertentu (lihat bagian 7). '
        'Keduanya sudah terisi bawaan; biarkan apa adanya bila tidak perlu diubah.',
        'Klik Tanya dan tunggu. Di mesin CPU, jawaban biasanya selesai dalam 40–170 detik.',
        'Jawaban muncul pada tab Jawaban; teks Yunani ayat yang dikutip ada pada tab '
        'Teks Asli (Yunani).',
    ])
    gambar(doc, '08-konsol.png', 'Konsol Tanya RAG setelah menjawab pertanyaan "Roma 8:15".')

    doc.add_heading('4.1 Dua jenis pertanyaan', level=2)
    tabel(doc, 'Perilaku pencarian menurut bentuk pertanyaan', ['Bentuk pertanyaan', 'Jalur', 'Perilaku'], [
        ['Menyebut nomor ayat — "Roma 8:1", "8:29–30"',
         'Pencarian Langsung', 'Ayat diambil langsung sesuai nomor; variannya ikut disajikan. '
                               'Cara paling andal dan paling cepat.'],
        ['Berupa konsep — "mengapa tidak ada penghukuman?"',
         'Pencarian Hybrid', 'Pencarian vektor dan pencarian kata digabung. Ayat yang mirip '
                             'makna maupun yang memuat kata kunci sama-sama dipertimbangkan.'],
    ], lebar=[6.0, 3.6, 6.6])

    catatan(doc, 'Tips:',
            'Untuk pertanyaan tentang satu ayat tertentu, sebutkan nomornya. Untuk pertanyaan '
            'doktrinal yang luas, sebutkan istilah khasnya (misalnya "predestinasi") — '
            'istilah itu akan diperluas otomatis ke padanannya.')

    # ------------------------------------------------------------ Bagian 5
    doc.add_heading('5. Membaca jawaban dan riwayat kueri', level=1)
    doc.add_paragraph(
        'Setiap pertanyaan tersimpan permanen, lengkap dengan ayat yang diambil dan skornya. '
        'Buka Kueri → Riwayat Kueri untuk menelusurinya.')
    gambar(doc, '09-riwayat-jawaban.png', 'Form riwayat kueri: status, latensi, token, dan jawaban.')
    tabel(doc, 'Arti field pada riwayat kueri', ['Field', 'Arti'], [
        ['Status', 'Draf (belum dijalankan), Berjalan, Berhasil, atau Galat'],
        ['Jalur', 'Pencarian Langsung atau Pencarian Hybrid'],
        ['Latensi', 'Waktu total dari pertanyaan sampai jawaban selesai'],
        ['Token Prompt / Jawaban', 'Banyaknya token yang masuk ke model dan yang dihasilkan'],
        ['Ayat Terambil', 'Daftar ayat beserta peringkat vektor, peringkat kata, dan skor gabungan'],
        ['Pengaturan RAG', 'Preset yang dipakai kueri itu (endpoint, top-k, temperature)'],
        ['Templat Prompt', 'Templat instruksi yang dipakai; bila kosong berarti mengikuti Pengaturan RAG'],
    ], lebar=[4.2, 12.0])

    doc.add_heading('5.1 Tab Teks Asli (Yunani)', level=2)
    doc.add_paragraph(
        'Tab ini menampilkan bahasa asli dari ayat yang benar-benar dikutip dalam jawaban, '
        'bukan sekadar ayat yang terambil. Karena itu ia bisa menampilkan ayat yang masuk '
        'sebagai konteks perikop, dan menandainya dengan jelas.')
    gambar(doc, '10-riwayat-teks-asli.png',
           'Tab Teks Asli (Yunani): ayat yang dikutip, ditandai hasil pencarian atau konteks perikop.')
    butir(doc, [
        '(hasil pencarian) — ayat itu benar-benar terambil oleh mesin pencari.',
        '(konteks perikop) — ayat itu disertakan karena satu perikop dengan ayat yang terambil, '
        'supaya alur argumen tidak terputus.',
        'Setiap ayat ditampilkan dalam tiga bentuk: berdiakritik, transliterasi, dan tanpa aksen.',
    ])

    # ------------------------------------------------------------ Bagian 6
    doc.add_heading('6. Menjalankan kueri dari Riwayat Kueri', level=1)
    doc.add_paragraph(
        'Riwayat Kueri bisa juga dipakai sebagai antrean: buat catatan pertanyaan lebih dulu, '
        'lalu jalankan kapan saja.')
    langkah(doc, [
        'Buka Kueri → Riwayat Kueri, klik New.',
        'Isi Pertanyaan. Kolom lain boleh dibiarkan; Konfigurasi juga boleh dipilih.',
        'Klik Simpan. Status akan menjadi Draf.',
        'Klik tombol Jalankan Kueri pada bagian atas form (atau ikon ▶ pada daftar).',
        'Setelah selesai, form memuat ulang sendiri dan jawaban tampil.',
    ])
    catatan(doc, 'Menjalankan ulang:',
            'Menekan Jalankan Kueri pada catatan yang sudah berhasil akan menjalankan ulang '
            'dan mengganti hasil sebelumnya. Daftar ayat terambil ikut dibersihkan lebih dulu, '
            'jadi tidak ada duplikat.')

    # ------------------------------------------------------------ Bagian 7
    doc.add_heading('7. Memilih Pengaturan RAG per kueri', level=1)
    doc.add_paragraph(
        'Pengaturan RAG menyimpan parameter pencarian dan model. Beberapa pengaturan boleh '
        'aktif sekaligus sebagai preset — misalnya satu preset "cepat" dengan jawaban pendek, '
        'dan satu preset "lengkap" dengan jawaban panjang. Pada konsol, preset dipilih per '
        'pertanyaan.')
    gambar(doc, '05-pengaturan-rag.png', 'Form Pengaturan RAG: endpoint, model, dan parameter pencarian.')
    tabel(doc, 'Parameter yang biasa disesuaikan', ['Parameter', 'Arti', 'Saran'], [
        ['Chat / Embedding URL', 'Alamat layanan model bahasa dan model embedding', 'Jangan diubah kecuali diminta administrator'],
        ['Kandidat Vektor / Full-text', 'Jumlah ayat yang dipertimbangkan sebelum dipilih', '20 sudah memadai'],
        ['Konstanta RRF', 'Penyeimbang penggabungan dua peringkat', '60 (bawaan)'],
        ['Masuk Konteks', 'Jumlah ayat yang akhirnya dikirim ke model', '5'],
        ['Temperature', 'Kreativitas jawaban', '0,1–0,3 agar jawaban patuh pada konteks'],
        ['Maks Token Jawaban', 'Batas panjang jawaban', '200–300 untuk kueri cepat'],
    ], lebar=[4.6, 7.0, 4.6])
    catatan(doc, 'Penting:',
            'Preset harus memakai model embedding yang sama dengan yang dipakai saat data '
            'di-embed. Bila berbeda, kueri akan ditolak dengan pesan yang menyebut kedua model — '
            'ini disengaja, karena membandingkan vektor dari model berbeda menghasilkan '
            'peringkat palsu.')

    doc.add_heading('7.1 Templat Prompt per kueri', level=2)
    doc.add_paragraph(
        'Templat prompt adalah instruksi yang dikirim ke model sebelum pertanyaan Anda — misalnya '
        'perintah untuk selalu menyebut nomor ayat, atau membatasi jawaban menjadi dua kalimat. '
        'Pada konsol, templat bisa diganti khusus untuk satu kueri tanpa mengubah pengaturan lain.')
    gambar(doc, '11-konsol-pengaturan.png',
           'Konsol dengan pilihan Pengaturan RAG dan Templat Prompt sebelum pertanyaan diajukan.')
    langkah(doc, [
        'Buka Kueri → Tanya RAG.',
        'Perhatikan dua pilihan di bawah kotak pertanyaan: Pengaturan RAG dan Templat Prompt.',
        'Templat Prompt otomatis mengikuti templat dari Pengaturan RAG yang dipilih.',
        'Bila ingin instruksi berbeda untuk kueri ini saja, ganti Templat Prompt; '
        'Pengaturan RAG tidak ikut berubah.',
        'Ajukan pertanyaan seperti biasa. Templat yang dipakai tercatat pada Riwayat Kueri.',
    ])
    catatan(doc, 'Membuat templat baru:',
            'Buka Konfigurasi → Templat Prompt → New. Isi nama, versi, dan instruksinya. '
            'Templat yang aktif akan muncul pada pilihan di konsol. Untuk memakai templat itu '
            'sebagai bawaan, setel pada Pengaturan RAG.')

    # ------------------------------------------------------------ Bagian 8
    doc.add_heading('8. Pengelolaan data (RAG Manager)', level=1)
    doc.add_paragraph(
        'Bagian ini hanya untuk RAG Manager. Urutannya penting: impor → chunking → embedding.')
    doc.add_heading('8.1 Impor dataset', level=2)
    doc.add_paragraph('Menu Konfigurasi → Impor Dataset… memuat dataset Roma 8 ke database.')
    langkah(doc, [
        'Buka Konfigurasi → Impor Dataset…',
        'Unggah berkas JSON, atau isi path di server (bawaan /opt/odoo18/rag-data/roma8.json).',
        'Klik Impor. Hasilnya tercatat di Konfigurasi → Batch Impor.',
    ])
    catatan(doc, 'Aman diulang:',
            'Impor bersifat idempoten — data dicocokkan per (kitab, pasal, ayat) dan '
            '(kitab, pasal, rentang perikop). Impor kedua memperbarui, bukan menggandakan.')

    doc.add_heading('8.2 Chunking', level=2)
    doc.add_paragraph(
        'Chunking membentuk unit pencarian per ayat dan menyusun teks yang akan di-embed. '
        'Tanpa langkah ini, ayat berstatus Draf dan tidak akan pernah ikut pencarian.')
    langkah(doc, [
        'Buka Konfigurasi → Jalankan Chunking.',
        'Biarkan "Hanya yang perlu diproses" tercentang.',
        'Klik Jalankan. Status ayat berubah menjadi Ter-chunk.',
    ])

    doc.add_heading('8.3 Embedding', level=2)
    doc.add_paragraph(
        'Embedding mengubah teks menjadi vektor sehingga pencarian makna bisa dilakukan. '
        'Proses ini berjalan otomatis lewat penjadwal setiap 5 menit untuk chunk yang menunggu.')
    gambar(doc, '06-chunk.png', 'Daftar chunk beserta status dan waktu embedding.')
    butir(doc, [
        'Untuk memaksa proses lebih cepat: pilih chunk lalu klik Re-embed.',
        'Pada form ayat tersedia tombol Re-embed Chunk untuk ayat tersebut.',
        'Bila gagal berulang, kolom Galat Terakhir menyimpan pesan penyebabnya.',
        'Mengubah teks ayat otomatis menandai chunk-nya kotor sehingga di-embed ulang.',
    ])

    doc.add_heading('8.4 Ekspansi kueri', level=2)
    doc.add_paragraph(
        'Pertanyaan umum seperti "keselamatan" bisa tidak menemukan ayat yang tepat karena '
        'ayat itu memakai kata lain. Ekspansi kueri menambahkan padanan istilah ke pencarian.')
    gambar(doc, '07-ekspansi.png', 'Daftar istilah ekspansi beserta catatannya.')
    doc.add_paragraph(
        'Contoh bawaan: istilah keselamatan diperluas ke diselamatkan, penebusan, dibenarkan, '
        'dimuliakan, dipanggil, ditetapkan, dan serupa. Berkat itu Roma 8:29–30 ikut ditemukan '
        'meskipun pertanyaannya tidak menyebut "predestinasi" atau "dimuliakan".')
    catatan(doc, 'Menambah istilah:',
            'Klik New, isi Istilah, lalu tambahkan baris Padanan. Perubahan berlaku pada kueri '
            'berikutnya tanpa perlu menyalakan ulang layanan.')

    # ------------------------------------------------------------ Bagian 9
    doc.add_heading('9. Alur kerja yang disarankan', level=1)
    tabel(doc, 'Alur pemakaian harian', ['Tahap', 'Tindakan', 'Penanggung jawab'], [
        ['1', 'Pastikan data sudah diimpor (Batch Impor menunjukkan status Selesai)', 'RAG Manager'],
        ['2', 'Jalankan Chunking bila ada ayat baru', 'RAG Manager'],
        ['3', 'Pastikan semua chunk berstatus Ter-embed', 'RAG Manager'],
        ['4', 'Ajukan pertanyaan lewat Tanya RAG', 'Semua pengguna'],
        ['5', 'Periksa tab Teks Asli untuk memastikan kutipan sesuai', 'Semua pengguna'],
        ['6', 'Bila jawaban kurang lengkap, ulangi dengan nomor ayat atau istilah yang lebih khas',
         'Semua pengguna'],
        ['7', 'Bila sering meleset, tambahkan padanan pada Ekspansi Kueri', 'RAG Manager'],
    ], lebar=[1.6, 11.0, 3.6])

    # ----------------------------------------------------------- Bagian 10
    doc.add_heading('10. Pemecahan masalah', level=1)
    tabel(doc, 'Gejala, penyebab, dan penanganan', ['Gejala', 'Kemungkinan penyebab', 'Penanganan'], [
        ['Halaman tidak bisa dibuka sama sekali',
         'Layanan Odoo berhenti',
         'Pastikan layanan hidup, lalu buka log bila masih gagal (lihat di bawah)'],
        ['Kueri berjalan sangat lama lalu halaman gagal',
         'Jawaban melebihi batas waktu',
         'Kurangi Maks Token Jawaban, atau pakai pertanyaan bernomor ayat'],
        ['Jawaban tidak menyebut ayat yang Anda harapkan',
         'Ayat itu tidak terambil, atau hanya masuk sebagai konteks',
         'Sebutkan nomor ayatnya, atau tambahkan padanan istilah pada Ekspansi Kueri'],
        ['Jawaban terpotong di tengah',
         'Batas token jawaban tercapai',
         'Naikkan Maks Token Jawaban pada Pengaturan RAG'],
        ['Chunk berstatus Galat',
         'Layanan embedding tidak merespons',
         'Periksa pesan pada Galat Terakhir, lalu klik Re-embed setelah layanan pulih'],
        ['Ayat baru tidak pernah muncul di jawaban',
         'Belum di-chunk atau belum di-embed',
         'Jalankan Chunking, lalu tunggu penjadwal embedding atau tekan Re-embed'],
        ['Tombol Jalankan Kueri tidak terlihat',
         'Status bukan Draf atau Galat',
         'Buat catatan baru, atau jalankan ulang dari catatan yang masih Draf'],
    ], lebar=[4.6, 5.2, 6.4])

    doc.add_heading('10.1 Bila aplikasi tidak dapat diakses', level=2)
    doc.add_paragraph('Tiga pemeriksaan cepat di server, berurutan:')
    par = doc.add_paragraph()
    kode(par, 'systemctl status odoo18.service')
    par = doc.add_paragraph()
    kode(par, 'tail -50 /var/log/odoo18/odoo18.log')
    par = doc.add_paragraph()
    kode(par, 'curl -o /dev/null -w "%{http_code}" http://127.0.0.1:8069/web/login')
    doc.add_paragraph(
        'Kode 303 berarti layanan sehat (mengalihkan ke halaman masuk). Layanan disetel untuk '
        'menyalakan diri kembali bila berhenti mendadak, tetapi pemeriksaan manual tetap '
        'disarankan bila gangguan berulang.')

    # ----------------------------------------------------------- Bagian 11
    doc.add_heading('11. Batasan dan tips kualitas', level=1)
    butir(doc, [
        'Model berjalan di CPU tanpa kartu grafis. Jawaban panjang memerlukan puluhan detik '
        'sampai beberapa menit; ini normal.',
        'Model dapat melewatkan ayat yang hanya menjadi konteks perikop, meskipun ayat itu ada '
        'pada konteks yang dikirim. Untuk memastikan ayat tertentu dibahas, sebutkan nomornya.',
        'Pertanyaan sangat umum menyebar ke banyak ayat. Pertanyaan yang menyebut istilah khas '
        'atau nomor ayat memberi hasil jauh lebih baik.',
        'Varian tekstual yang tersedia berasal dari apparatus Robinson-Pierpont (perbandingan '
        'dengan Nestle-Aland dan Editio Critica Maior), bukan seluruh saksi naskah.',
        'Teks Indonesia memakai AYT, bukan Terjemahan Baru LAI. Perbedaan pilihan kata karena '
        'hal ini wajar dan bukan kesalahan aplikasi.',
    ])

    # ----------------------------------------------------------- Bagian 12
    doc.add_page_break()
    doc.add_heading('12. Lampiran: sumber data, lisensi, dan istilah', level=1)
    doc.add_heading('12.1 Sumber data', level=2)
    tabel(doc, 'Sumber teks dan lisensinya', ['Bahasa', 'Edisi', 'Lisensi'], [
        ['Yunani', 'Robinson-Pierpont 2018 (Byzantine Textform), dengan parsing dan nomor Strong',
         'Public domain'],
        ['Inggris', 'King James Version 1769', 'Public domain (di luar Inggris)'],
        ['Indonesia', 'AYT — Alkitab Yang Terbuka, © 2011–2024 YLSA-AYT',
         'Non-komersial, wajib atribusi'],
        ['Leksikon', "Strong's Greek Dictionary (Open Scriptures)", 'Public domain'],
    ], lebar=[3.0, 9.4, 3.8])

    doc.add_heading('12.2 Istilah', level=2)
    tabel(doc, 'Daftar istilah', ['Istilah', 'Arti dalam aplikasi ini'], [
        ['Ayat (child)', 'Unit terkecil yang menyimpan teks; menjadi dasar unit pencarian'],
        ['Perikop (parent)', 'Kelompok ayat yang menjadi konteks; disertakan utuh agar alur terjaga'],
        ['Chunk', 'Unit yang di-embed dan dicari. Satu chunk mewakili satu ayat'],
        ['Embedding', 'Representasi angka dari teks yang memungkinkan pencarian berdasarkan makna'],
        ['Hybrid search', 'Penggabungan pencarian makna (vektor) dan pencarian kata (full-text)'],
        ['RRF', 'Reciprocal Rank Fusion — cara menggabungkan dua peringkat menjadi satu'],
        ['Ekspansi kueri', 'Penambahan padanan istilah agar ayat dengan kata berbeda tetap ditemukan'],
        ['Varian tekstual', 'Perbedaan bacaan antar tradisi naskah pada ayat yang sama'],
        ['Status Ter-embed', 'Ayat sudah punya vektor dan siap ikut pencarian'],
    ], lebar=[4.2, 12.0])

    doc.add_paragraph()
    catatan(doc, 'Tentang dokumen ini:',
            'Panduan disusun dari aplikasi yang berjalan dan diuji pada 21 November 2026. '
            'Tangkapan layar diambil langsung dari antarmuka, bukan ilustrasi. Bila antarmuka '
            'berubah setelah pembaruan modul, sebagian gambar mungkin tampak berbeda.')

    doc.save(OUT)
    print(f"tersimpan: {OUT} ({OUT.stat().st_size:,} bytes)")
    print(f"gambar: {gambar_ke}, tabel: {tabel_ke}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
