# Benchmark & Infrastruktur llama.cpp — RAG Roma 8

Tanggal: 2026-11-21 · Host: `192.168.18.222` (`nms@nms-zabbix`) · Fase 2 TASK.md

---

## 1. Masalah awal yang diselesaikan

Sebelum intervensi, `llama-server` memuat **gpt-oss-20b-Q4_K_M (12 GB)** sebagai model dinamis di bawah router port 7070.

| Metrik | Sebelum | Sesudah |
|---|---|---|
| Swap terpakai | **10.696 MB** | **1.418 MB** (langsung setelah unload) |
| `VmSwap` proses 20B | **9.455 MB** | proses dihentikan |
| RAM `available` | 6.913 MB | 9.188 MB |
| Model aktif | 20B (di luar anggaran) | 7B / 4B (sesuai PLAN) |

Model dilepas dengan `POST /models/unload` ke router — bukan mematikan service, sehingga router di port 7070 tetap hidup.

---

## 2. Model yang disiapkan

| Model | Berkas | Ukuran | Peran |
|---|---|---|---|
| `bge-m3-Q8_0` | `bge-m3-Q8_0.gguf` | 605 MB | embedding utama, **1024 dim** |
| `Qwen2.5-7B-Instruct-Q4_K_M` | 4.466 MB | 4,4 GB | **chat default** |
| `Qwen3-4B-Q4_K_M` | 2.382 MB | 2,3 GB | cadangan ringan |

Diunduh dari HuggingFace (`gpustack/bge-m3-GGUF`, `bartowski/Qwen2.5-7B-Instruct-GGUF`, `Qwen/Qwen3-4B-GGUF`), tersimpan di `/home/nms/llama.cpp/models/`.

---

## 3. Layanan (systemd)

| Unit | Port | Bind | Model | Threads | Status |
|---|---|---|---|---|---|
| `llama-embed.service` | 8080 | 127.0.0.1 | bge-m3 Q8_0 | 6 | **enabled + active** |
| `llama-chat.service` | 8081 | 127.0.0.1 | Qwen2.5-7B Q4_K_M | 8 | **enabled + active** |
| `llama-chat-4b.service` | 8092 | 127.0.0.1 | Qwen3-4B Q4_K_M | 8 | disabled (cadangan) |
| `llama-server.service` | 7070 | 0.0.0.0 | router lama | — | tidak disentuh |

Parameter bersama: `--ctx-size 8192`, `--cache-type-k q8_0`, `--cache-type-v q8_0`, `--flash-attn on`, `--no-webui`.

Kedua layanan RAG **hanya listen di loopback** — berbeda dari router lama yang terbuka di `0.0.0.0` dengan API key di argv.

Unit tersimpan di repo: [deploy/llama-embed.service](../deploy/llama-embed.service), [deploy/llama-chat.service](../deploy/llama-chat.service).

---

## 4. Hasil benchmark

Prompt uji: konteks Roma 8:1–11 (Yunani/KJV/LAI) + instruksi eksposisi, **968 token**. Output 256 token. Threads 8.

| Model | Prompt eval | Generasi | Wall (256 tok) | RSS | Swap |
|---|---|---|---|---|---|
| **Qwen2.5-7B** | 37,4 tok/s | **8,3 tok/s** | 30,7 s | 7.689 MB | 35 MB |
| **Qwen3-4B** | **53,7 tok/s** | **12,3 tok/s** | 21,1 s | 4.765 MB | — |

### Prompt caching terbukti aktif

Permintaan kedua dengan prompt identik hanya memproses **1 token prompt** (vs 968 pada permintaan pertama). Ini penting untuk konsol RAG yang mengulang system prompt panjang — hemat ±25 detik per kueri lanjutan.

### Embedding

| Uji | Hasil |
|---|---|
| Dimensi | **1024** (cocok untuk `vector(1024)`) |
| Norma L2 | 1.0 (sudah ternormalisasi) |
| Latensi 1 teks | 0,07 s (warm), 0,46 s (cold) |
| Batch 5 teks | 0,24 s |

---

## 5. Beban memori gabungan

Dengan Odoo 18 + PostgreSQL 16 + Odoo/Zabbix (`mysqld`) + embed + chat berjalan bersamaan:

```
Mem:   total 15.498 MB   used 7.667 MB   available 7.830 MB
Swap:  total 16.383 MB   used 3.679 MB
RAM terpakai: 49,5%          ← target PLAN: < 85%  ✅
```

Penghuni swap yang tersisa **bukan** dari tumpukan RAG, melainkan layanan lama yang idle:

| Proses | Swap |
|---|---|
| `docling-serve` | 840 MB |
| `python` (pid 4928) | 786 MB |
| `python3` (pid 4095668) | 560 MB |
| `mysqld` (Zabbix) | 188 MB |
| **`llama-chat`** | **35 MB** |
| **`llama-embed`** | **134 MB** |

Artinya anggaran memori PLAN (6–8 GB untuk AI) terpenuhi: 7,7 GB + 0,77 GB ≈ **8,4 GB**, dan sistem tetap di 49,5%.

> Catatan: RSS `llama-embed` sempat terbaca 771 MB lalu turun ke 16 MB — normal, karena bobot model di-*mmap* dan halamannya berpindah ke page cache. Latensi tetap 0,07 s.

---

## 6. Keputusan

**Qwen2.5-7B-Instruct sebagai default.** Alasannya bukan kecepatan (4B 48% lebih cepat), melainkan kualitas eksposisi Bahasa Indonesia dan kepatuhan *grounding* — dua hal yang menjadi inti PLAN. 8,3 tok/s menghasilkan jawaban 300 token dalam ±36 detik, masih di dalam batas HTTP timeout 120–180 detik yang dirancang.

**Qwen3-4B tetap tersedia** sebagai cadangan bila memori mengetat atau diinginkan respons lebih cepat:

```bash
sudo systemctl stop llama-chat && sudo systemctl start llama-chat-4b
```

---

## 7. Temuan kualitas yang perlu ditindaklanjuti

Smoke test pada 7B, prompt: *"Apa perbedaan tekstual Roma 8:1 antara RP/KJV dan LAI?"*

Model menjawab benar bahwa `κατάκριμα` = penghukuman, **tetapi melewatkan varian tekstual yang sebenarnya**: klausa `μὴ κατὰ σάρκα περιπατοῦσιν ἀλλὰ κατὰ πνεῦμα` ada di Robinson-Pierpont/KJV namun **tidak** ada di LAI. Model malah mengarang "perbedaan" pada penerjemahan kata yang sama.

Penyebab: konteks diberi tanpa penanda eksplisit bahwa klausa itu absen di LAI. Tindakan untuk Fase 6–7:

1. *Context Builder* harus menyertakan penanda eksplisit, mis. `[klausa tidak ada di LAI]`, bukan hanya tiga teks berdampingan.
2. *System prompt* perlu instruksi konkret: bandingkan **kehadiran klausa**, bukan hanya pilihan kata.
3. Pertanyaan varian tekstual sebaiknya di-*route* ke jalur `direct lookup` yang menyajikan metadata varian, bukan diserahkan pada inferensi LLM.

### Status: **sudah ditangani** (Fase 5–7)

| Tindakan | Implementasi | Bukti |
|---|---|---|
| Penanda varian eksplisit | `Context Builder` mencetak blok `[VARIAN TEKSTUAL]` | Roma 8:1 → *"NA MENGHILANGKAN klausa …, klausa itu ADA pada bacaan Byzantine"* |
| Instruksi membandingkan kehadiran klausa | Templat prompt **v2** | jawaban menyebut klausa yang hilang, bukan mengarang perbedaan kata |
| Varian sebagai data, bukan inferensi | tabel `rag_variant` (21 baris) | `NA/omission` untuk 8:1 tersimpan terstruktur |
| Routing varian | rute `direct` untuk nomor ayat | kueri "Roma 8:1" menyebut varian dengan benar |

Sisa keterbatasan: model 7B tetap bisa melewatkan ayat konteks yang tidak ditandai hasil pencarian — lihat [MODUL-ODOO.md](MODUL-ODOO.md) §13.

---

## 8. Reproduksi

```bash
# benchmark (dari dalam server, karena port hanya loopback)
python3 /tmp/ragbench/bench_llama.py --port 8081 --model qwen2.5-7b-instruct
python3 /tmp/ragbench/bench_llama.py --port 8092 --model qwen3-4b

# dari laptop, lewat helper SSH
python3 scripts/rrun.py 'python3 /tmp/ragbench/bench_llama.py --port 8081 --model qwen2.5-7b-instruct'
```

Skrip sumber: [scripts/bench_llama.py](../scripts/bench_llama.py).
