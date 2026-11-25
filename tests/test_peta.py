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


def test_popup_aman_untuk_callsign_nan_dan_pd_na():
    b = pd.Series({
        "icao24": "8a0001", "callsign": float("nan"), "maskapai": "Garuda Indonesia",
        "negara_asal": "Indonesia", "fase": "Jelajah", "alt_baro_m": pd.NA, "kecepatan_kmh": 800.0,
    })
    teks = peta.popup_pesawat(b)
    assert "(tanpa callsign)" in teks
    assert "<td>Ketinggian</td><td>- (-)</td>" in teks


def test_heatmap_membuang_koordinat_inf():
    jejak = pd.DataFrame({"lat": [-6.1, float("inf"), -7.0], "lon": [106.6, 107.0, float("-inf")]})
    teks = _html(peta.peta_heatmap(jejak))
    assert "Infinity" not in teks
    assert "[-6.1, 106.6]" in teks
