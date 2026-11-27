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


def test_popup_tanpa_bandara_tidak_tampil_nan():
    for kosong in (float("nan"), "-"):
        teks = peta.popup_pesawat(pd.Series({"callsign": "GIA1", "bandara_terdekat": kosong, "jarak_bandara_km": float("nan")}))
        assert "Bandara terdekat" not in teks
    teks = peta.popup_pesawat(pd.Series({"callsign": "GIA1", "bandara_terdekat": "CGK", "jarak_bandara_km": 12.0}))
    assert "CGK (12 km)" in teks


def test_angka_tak_hingga_tidak_tampil_inf():
    assert peta._teks(float("inf"), " m") == "-"
    assert peta._teks(1234.5, " m") == "1,234 m"
    assert "rotate(0deg)" in peta.ikon_pesawat("#fff", float("inf")).options["html"]


def test_tooltip_callsign_nan_memakai_icao24():
    pesawat = pd.DataFrame([{
        "icao24": "8a0abc", "callsign": float("nan"), "maskapai": float("nan"), "negara_asal": "Indonesia",
        "lat": -6.1, "lon": 106.6, "arah": 90.0,
    }])
    teks = _html(peta.peta_pesawat(pesawat))
    assert "nan ·" not in teks
    assert "8a0abc · " in teks
