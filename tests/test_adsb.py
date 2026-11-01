"""Tes modul adsb: tebakan negara, konversi satuan, penggabungan lingkaran, dan rute cadangan."""
from __future__ import annotations

import pandas as pd
import pytest

from src import adsb, muat_data, opensky

PESAWAT = [
    {"hex": "8A04D7", "flight": "GIA875  ", "r": "PK-GPW", "t": "A333", "alt_baro": 2100, "alt_geom": 2250,
     "gs": 187.7, "track": 68.77, "baro_rate": -128, "squawk": "3736", "lat": -6.165, "lon": 106.514,
     "seen_pos": 0.0, "seen": 0.0, "spi": 0, "type": "adsb_icao"},
    {"hex": "76cd11", "flight": "SIA123", "r": "9V-SHA", "alt_baro": "ground", "gs": 5, "track": 10,
     "lat": 1.35, "lon": 103.99, "seen": 2.0, "type": "mlat"},
    {"hex": "abcdef", "flight": "", "alt_baro": 35000, "lat": 40.0, "lon": -70.0, "type": "adsb_icao"},  # di luar kotak
    {"hex": "8a9999", "lat": None, "lon": 110.0},  # tanpa koordinat
]


# ---------------------------------------------------------------- negara
@pytest.mark.parametrize("registrasi, icao, negara", [
    ("PK-GPW", None, "Indonesia"),
    ("9V-SHA", None, "Singapore"),
    ("9M-MXA", None, "Malaysia"),
    ("B-HLR", None, "Hong Kong"),
    ("B-1234", None, "China"),
    ("N12345", None, "United States"),
    ("VP-BAA", None, "Bermuda"),
    ("", "8a04d7", "Indonesia"),
    ("", "7c1234", "Australia"),
    (None, "zz", adsb.NEGARA_TIDAK_DIKETAHUI),
    (None, None, adsb.NEGARA_TIDAK_DIKETAHUI),
])
def test_negara_registrasi(registrasi, icao, negara):
    assert adsb.negara_registrasi(registrasi, icao) == negara


# ---------------------------------------------------------------- konversi
def test_ac_ke_dataframe_kolom_dan_satuan():
    df = adsb.ac_ke_dataframe(PESAWAT, waktu_snapshot=1_700_000_000)
    assert list(df.columns)[: len(adsb.KOLOM)] == adsb.KOLOM
    assert set(opensky.KOLOM_STATE) - {"sensor"} <= set(df.columns)
    assert len(df) == 2  # di luar kotak dan tanpa koordinat dibuang
    gia = df[df["icao24"] == "8a04d7"].iloc[0]
    assert gia["callsign"] == "GIA875"
    assert gia["negara_asal"] == "Indonesia"
    assert gia["alt_baro_m"] == pytest.approx(2100 * 0.3048)
    assert gia["kecepatan_ms"] == pytest.approx(187.7 * 0.514444)
    assert gia["laju_vertikal"] == pytest.approx(-128 * 0.00508)
    assert not gia["di_darat"]
    assert gia["sumber_posisi"] == 0
    assert gia["waktu_snapshot"] == 1_700_000_000
    assert str(gia["waktu"].tz) == "UTC"


def test_ac_ke_dataframe_di_darat_dan_mlat():
    df = adsb.ac_ke_dataframe(PESAWAT, waktu_snapshot=1_700_000_000)
    sia = df[df["icao24"] == "76cd11"].iloc[0]
    assert sia["di_darat"]
    assert pd.isna(sia["alt_baro_m"])
    assert sia["sumber_posisi"] == 2
    assert sia["waktu_kontak"] == 1_700_000_000 - 2


def test_ac_ke_dataframe_kosong():
    df = adsb.ac_ke_dataframe([], waktu_snapshot=0)
    assert df.empty and "negara_asal" in df.columns


# ---------------------------------------------------------------- gabungan lingkaran
class _Respons:
    def __init__(self, status, data=None):
        self.status_code = status
        self._data = data or {}

    def json(self):
        return self._data


class _Sesi:
    """Sesi palsu: jawaban per urutan panggilan."""

    def __init__(self, jawaban):
        self.jawaban = list(jawaban)
        self.url = []

    def get(self, url, timeout=None, headers=None):
        self.url.append(url)
        return self.jawaban.pop(0)


def test_ambil_semua_gabung_dan_lewati_yang_gagal():
    sesi = _Sesi([
        _Respons(200, {"now": 1_700_000_000_000, "ac": [PESAWAT[0], PESAWAT[1]]}),
        _Respons(429),
        _Respons(200, {"now": 1_700_000_005_000, "ac": [PESAWAT[1], PESAWAT[2]]}),
    ])
    daftar, waktu, info = adsb.ambil_semua(titik=[(0, 100), (0, 120), (0, 140)], jeda=0, session=sesi)
    assert info == {"berhasil": 2, "total": 3}
    assert waktu == 1_700_000_005
    assert sorted(a["hex"].lower() for a in daftar) == ["76cd11", "8a04d7", "abcdef"]
    assert "dist/1000" in sesi.url[0]


def test_ambil_semua_semua_gagal():
    sesi = _Sesi([_Respons(429), _Respons(500)])
    with pytest.raises(adsb.AdsbError):
        adsb.ambil_semua(titik=[(0, 100), (0, 120)], jeda=0, session=sesi)


# ---------------------------------------------------------------- rute cadangan
def test_muat_live_pakai_adsb_dulu(monkeypatch):
    df = adsb.ac_ke_dataframe(PESAWAT, waktu_snapshot=1)
    monkeypatch.setattr(adsb, "ambil_dataframe", lambda session=None: (df, {"berhasil": 2, "total": 2}))
    hasil, sumber, pesan = muat_data.muat_live_atau_sampel()
    assert sumber == "live" and "adsb.lol" in pesan and len(hasil) == 2


def test_muat_live_jatuh_ke_sampel(monkeypatch):
    def gagal(session=None):
        raise adsb.AdsbError("adsb.lol mati")

    def gagal_opensky(*a, **k):
        raise opensky.OpenSkyError("OpenSky mati")

    monkeypatch.setattr(adsb, "ambil_dataframe", gagal)
    monkeypatch.setattr(opensky, "ambil_dataframe", gagal_opensky)
    hasil, sumber, pesan = muat_data.muat_live_atau_sampel()
    assert sumber == "sampel" and "adsb.lol mati" in pesan and "OpenSky mati" in pesan
    assert not hasil.empty
