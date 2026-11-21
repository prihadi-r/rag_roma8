#!/usr/bin/env python3
"""Benchmark llama-server: prompt eval & generation speed (CPU-only).

Mengirim prompt bergaya RAG Roma 8 (±1.200 token) lalu melaporkan:
  - prompt_per_second (kecepatan prompt evaluation)
  - predicted_per_second (kecepatan generasi)
  - wall clock, jumlah token, RSS proses

Pemakaian:
    python3 bench_llama.py --port 8081 --model qwen2.5-7b-instruct
    python3 bench_llama.py --port 8092 --model qwen3-4b --runs 3
"""
import argparse
import json
import os
import time
import urllib.request

# Prompt realistis: konteks perikop + instruksi eksposisi (gaya Context Builder Odoo)
KONTEKS = """KONTEKS AYAT (Roma 8:1-11)

[Roma 8:1 — Yunani]
Οὐδὲν ἄρα νῦν κατάκριμα τοῖς ἐν Χριστῷ Ἰησοῦ μὴ κατὰ σάρκα περιπατοῦσιν
ἀλλὰ κατὰ πνεῦμα.

[Roma 8:1 — KJV]
There is therefore now no condemnation to them which are in Christ Jesus,
who walk not after the flesh, but after the Spirit.

[Roma 8:1 — LAI/TB]
Demikianlah sekarang tidak ada penghukuman bagi mereka yang ada di dalam
Kristus Yesus.

[Roma 8:2 — LAI/TB]
Roh, yang memberi hidup telah memerdekakan kamu dalam Kristus dari hukum
dosa dan hukum maut.

[Roma 8:3 — LAI/TB]
Sebab apa yang tidak mungkin dilakukan hukum Taurat karena tak berdaya oleh
daging, telah dilakukan oleh Allah. Dengan jalan mengutus Anak-Nya sendiri
dalam daging yang sama dengan daging yang berdosa, Ia telah menjatuhkan
hukuman atas dosa di dalam daging.

[Roma 8:4 — LAI/TB]
supaya tuntutan hukum Taurat digenapi di dalam kita, yang tidak hidup
menurut daging, tetapi menurut Roh.

[Roma 8:5 — LAI/TB]
Sebab mereka yang hidup menurut daging, memikirkan hal-hal yang dari daging;
mereka yang hidup menurut Roh, memikirkan hal-hal yang dari Roh.

[Roma 8:6 — LAI/TB]
Karena keinginan daging adalah maut, tetapi keinginan Roh adalah hidup dan
damai sejahtera.

[Roma 8:7 — LAI/TB]
Sebab keinginan daging adalah perseteruan terhadap Allah, karena tidak
takluk kepada hukum Allah; hal ini memang tidak mungkin baginya.

[Roma 8:8 — LAI/TB]
Mereka yang hidup dalam daging tidak mungkin berkenan kepada Allah.

[Roma 8:9 — LAI/TB]
Tetapi kamu tidak hidup dalam daging, melainkan dalam Roh, jika memang Roh
Allah berdiam di dalam kamu. Tetapi jika orang tidak memiliki Roh Kristus,
ia bukan milik Kristus.

[Roma 8:10 — LAI/TB]
Tetapi jika Kristus ada di dalam kamu, maka tubuh memang mati karena dosa,
tetapi roh adalah hidup karena kebenaran.

[Roma 8:11 — LAI/TB]
Dan jika Roh Dia, yang telah membangkitkan Yesus dari antara orang mati,
berdiam di dalam kamu, maka Ia, yang telah membangkitkan Kristus Yesus dari
antara orang mati, akan menghidupkan juga tubuhmu yang fana itu oleh Roh-Nya,
yang berdiam di dalam kamu.
"""

INSTRUKSI = """INSTRUKSI:
Jawab HANYA berdasarkan konteks di atas. Jangan menambahkan ayat lain yang
tidak ada dalam konteks. Untuk setiap klaim, sebutkan nomor ayat dan kutipan
kata persis dari teks yang tersedia. Soroti perbedaan tekstual antara tradisi
Byzantine (Robinson-Pierpont/KJV) dan teks eklektik (LAI), bila ada.

PERTANYAAN: Apa dasar Paulus menyatakan "tidak ada penghukuman" dan bagaimana
argumen itu berlanjut sampai Roma 8:11? Jelaskan kata kunci Yunani yang
relevan beserta alasan gramatikalnya, lalu bandingkan pilihan kata KJV dengan
LAI. Akhiri dengan ringkasan tiga kalimat.
"""


def rss_of(port):
    """RSS proses llama-server yang memegang port tertentu (MB)."""
    try:
        out = os.popen("ss -ltnp 2>/dev/null | grep ':%d '" % port).read()
    except OSError:
        return None
    import re
    m = re.search(r"pid=(\d+)", out)
    if not m:
        return None
    try:
        with open("/proc/%s/status" % m.group(1)) as fh:
            for line in fh:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) // 1024
    except OSError:
        return None
    return None


def call(port, model, max_tokens, seed):
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Anda adalah asisten eksegesis Alkitab yang ketat grounding."},
            {"role": "user", "content": KONTEKS + "\n" + INSTRUKSI},
        ],
        "temperature": 0.2,
        "max_tokens": max_tokens,
        "seed": seed,
        "stream": False,
    }
    req = urllib.request.Request(
        "http://127.0.0.1:%d/v1/chat/completions" % port,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=900) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    wall = time.time() - t0
    return body, wall


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--max-tokens", type=int, default=256)
    ap.add_argument("--runs", type=int, default=2)
    args = ap.parse_args()

    print("model   : %s  (port %d)" % (args.model, args.port))
    print("maks tok: %d, runs: %d" % (args.max_tokens, args.runs))
    print("-" * 68)

    rows = []
    for i in range(args.runs):
        body, wall = call(args.port, args.model, args.max_tokens, seed=100 + i)
        t = body.get("timings", {}) or {}
        usage = body.get("usage", {}) or {}
        rows.append({
            "run": i + 1,
            "wall_s": round(wall, 2),
            "prompt_tok": t.get("prompt_n", usage.get("prompt_tokens")),
            "gen_tok": t.get("predicted_n", usage.get("completion_tokens")),
            "prompt_tps": round(t.get("prompt_per_second", 0), 1),
            "gen_tps": round(t.get("predicted_per_second", 0), 1),
        })
        r = rows[-1]
        print("run %d: prompt %s tok @ %s tok/s | gen %s tok @ %s tok/s | wall %ss"
              % (r["run"], r["prompt_tok"], r["prompt_tps"],
                 r["gen_tok"], r["gen_tps"], r["wall_s"]))

    rss = rss_of(args.port)
    gen = [r["gen_tps"] for r in rows if r["gen_tps"]]
    prm = [r["prompt_tps"] for r in rows if r["prompt_tps"]]
    print("-" * 68)
    print("RATA-RATA  prompt eval : %.1f tok/s" % (sum(prm) / len(prm) if prm else 0))
    print("RATA-RATA  generasi    : %.1f tok/s" % (sum(gen) / len(gen) if gen else 0))
    print("RSS proses             : %s MB" % rss)
    print("JSON: " + json.dumps({"model": args.model, "port": args.port,
                                "rss_mb": rss, "runs": rows}))


if __name__ == "__main__":
    main()
