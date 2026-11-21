"""Decoder kode morfologi Robinson-Pierpont → Bahasa Indonesia.

Spesifikasi mengikuti `source/README.md` repositori byztxt/byzantine-majority-text:
bentuk verba `V-tense-voice-mood[-person-number | -case-number-gender]`,
bentuk nominal `POS-case-number-gender[-degree]`.

Modul ini sengaja tidak mengimpor Odoo agar bisa diuji berdiri sendiri.
"""

# --- bagian ujaran ---------------------------------------------------------
POS = {
    'N': 'nomina',
    'A': 'adjektiva',
    'T': 'artikel',
    'D': 'pronomina demonstratif',
    'P': 'pronomina persona',
    'R': 'pronomina relatif',
    'X': 'pronomina taktentu',
    'I': 'pronomina interogatif',
    'K': 'pronomina korelatif',
    'F': 'pronomina refleksif',
    'V': 'verba',
    'ADV': 'adverbia',
    'CONJ': 'konjungsi',
    'PREP': 'preposisi',
    'PRT': 'partikel',
    'COND': 'partikel kondisional',
    'INJ': 'interjeksi',
    'HEB': 'kata Ibrani',
    'ARAM': 'kata Aram',
}

TENSE = {
    'P': 'present', 'I': 'imperfek', 'F': 'futur', 'A': 'aorist',
    'R': 'perfek', 'L': 'pluperfek',
}

VOICE = {
    'A': 'aktif', 'M': 'mediopasif (medium)', 'P': 'pasif',
    'E': 'medium atau pasif', 'D': 'deponen medium',
    'O': 'deponen pasif', 'N': 'deponen medipasif',
}

MOOD = {
    'I': 'indikatif', 'S': 'subjungtif', 'O': 'optatif',
    'M': 'imperatif', 'N': 'infinitif', 'P': 'partisip',
}

CASE = {'N': 'nominatif', 'G': 'genitif', 'D': 'datif', 'A': 'akusatif', 'V': 'vokatif'}
NUMBER = {'S': 'tunggal', 'P': 'plural'}
GENDER = {'M': 'maskulin', 'F': 'feminin', 'N': 'netral'}
PERSON = {'1': 'orang ke-1', '2': 'orang ke-2', '3': 'orang ke-3'}

# akhiran tambahan
EXTRA = {
    'S': 'superlatif',
    'C': 'komparatif',
    'N': 'bermakna negatif',
    'I': 'bermakna interogatif',
    'ATT': 'bentuk Attika',
}

_SEKUNDER = ('2A', '2F', '2R', '2L')

#: Hanya kelompok ini yang memakai pola kasus–jumlah–gender.
NOMINAL = {'N', 'A', 'T', 'D', 'P', 'R', 'X', 'I', 'K', 'F'}

#: Kode khusus yang tidak mengikuti pola kasus–jumlah–gender.
KODE_KHUSUS = {
    'PRI': 'nama diri',
    'LI': 'tidak berubah bentuk (indeclinable)',
    'T': 'bentuk singkat',
}


def _pisah(bagian: str):
    """Pisahkan awalan '2' (bentuk sekunder) dari tense/voice/mood."""
    if len(bagian) >= 3 and bagian[:2] in _SEKUNDER:
        return bagian[:2], bagian[2:]
    return None, bagian


def decode(kode: str) -> dict:
    """Kembalikan dict terstruktur: pos, tense, voice, mood, case, number, gender, person, extra, text."""
    kode = (kode or '').strip().upper()
    hasil = {
        'kode': kode, 'pos': None, 'tense': None, 'voice': None, 'mood': None,
        'case': None, 'number': None, 'gender': None, 'person': None,
        'extra': None, 'text': '',
    }
    if not kode:
        return hasil

    bagian = kode.split('-')
    pos = bagian[0]
    hasil['pos'] = POS.get(pos, pos.lower())
    label = [hasil['pos']]

    if pos == 'V' and len(bagian) >= 2:
        sekunder, sisa = _pisah(bagian[1])
        if sekunder and len(sisa) == 2:          # 2AAI → aorist kedua, aktif, indikatif
            tense, voice, mood = sekunder[1], sisa[0], sisa[1]
        elif not sekunder and len(sisa) == 3:    # AAI → aorist, aktif, indikatif
            tense, voice, mood = sisa[0], sisa[1], sisa[2]
        else:
            hasil['text'] = ', '.join(label + [b.lower() for b in bagian[1:] if b])
            return hasil
        hasil['tense'] = TENSE.get(tense, tense)
        hasil['voice'] = VOICE.get(voice, voice)
        hasil['mood'] = MOOD.get(mood, mood)
        label += [hasil['tense'], hasil['voice'], hasil['mood']]
        if sekunder:
            label.append('bentuk kedua')
        if len(bagian) >= 3:
            label += _urai_akhir(bagian[2], hasil)
        for sisa_bagian in bagian[3:]:
            _tambahan(sisa_bagian, hasil, label)
    elif pos in NOMINAL and len(bagian) >= 2:
        if bagian[1] in KODE_KHUSUS:
            label.append(KODE_KHUSUS[bagian[1]])
            hasil['extra'] = KODE_KHUSUS[bagian[1]]
        else:
            label += _urai_akhir(bagian[1], hasil)
        for sisa_bagian in bagian[2:]:
            _tambahan(sisa_bagian, hasil, label)
    else:
        # PRT-N, CONJ-N, ADV-I, ADV-S, -ATT: akhiran bukan kasus
        for sisa_bagian in bagian[1:]:
            _tambahan(sisa_bagian, hasil, label)

    hasil['text'] = ', '.join(b for b in label if b)
    return hasil


def _urai_akhir(bagian: str, hasil: dict) -> list[str]:
    """Urai '3S' (person+number) atau 'NSN' / '1AS' (case+number+gender)."""
    hasil_label = []
    sisa = bagian
    if sisa and sisa[0] in PERSON:
        hasil['person'] = PERSON[sisa[0]]
        hasil_label.append(hasil['person'])
        sisa = sisa[1:]
    if len(sisa) >= 1 and sisa[0] in CASE:
        hasil['case'] = CASE[sisa[0]]
        hasil_label.append(hasil['case'])
        sisa = sisa[1:]
    if len(sisa) >= 1 and sisa[0] in NUMBER:
        hasil['number'] = NUMBER[sisa[0]]
        hasil_label.append(hasil['number'])
        sisa = sisa[1:]
    if len(sisa) >= 1 and sisa[0] in GENDER:
        hasil['gender'] = GENDER[sisa[0]]
        hasil_label.append(hasil['gender'])
        sisa = sisa[1:]
    if sisa:
        hasil_label.append(sisa.lower())
    return hasil_label


def _tambahan(bagian: str, hasil: dict, label: list[str]) -> None:
    if bagian in EXTRA:
        hasil['extra'] = EXTRA[bagian]
        label.append(EXTRA[bagian])
    elif bagian:
        label.append(bagian.lower())


def to_text(kode: str) -> str:
    """Bentuk pendek untuk ditampilkan, mis. 'nomina, nominatif, tunggal, netral'."""
    return decode(kode)['text']


if __name__ == '__main__':  # uji cepat
    contoh = [
        'N-NSN', 'V-AAI-3S', 'V-PAP-DPM', 'A-NSN-N', 'ADV', 'PREP',
        'P-1AS', 'F-1DPM', 'V-AAN', 'V-2AAI-3S', 'T-DPM', 'PRT-N', 'COND', 'K-NPM',
    ]
    for k in contoh:
        print(f"{k:12} → {to_text(k)}")
