"""Tes kecil untuk src/peta.py: teks dari data harus di-escape sebelum masuk HTML peta."""

import pandas as pd

from src import peta


def _html(m) -> str:
    return m.get_root().render()


def test_tooltip_pesawat_dan_bandara_di_escape():
    pesawat = pd.DataFrame([{
        "icao24": "8a0001", "callsign": "<b>X</b>", "maskapai": "A&B", "negara_asal": "Indonesia",
        "lat": -6.1, "lon": 106.6, "arah": 90.0,
    }])
    bandara = pd.DataFrame([{"kode": "CGK", "nama": "<i>Soetta</i>", "kota": "Tangerang", "lat": -6.12, "lon": 106.65}])
    teks = _html(peta.peta_pesawat(pesawat, bandara))
    assert "<b>X</b>" not in teks
    assert "<i>Soetta</i>" not in teks
    assert "&lt;b&gt;X&lt;/b&gt;" in teks
