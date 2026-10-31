"""Tes untuk parsing OpenSky, tebakan maskapai, dan perhitungan. Jalankan: python -m pytest tests/ -v"""

import pandas as pd
import pytest

from src import analisis, maskapai, muat_data, opensky, peta

# ---------------------------------------------------------------- data uji
PAYLOAD = {
    "time": 1_793_469_804,
    "states": [
        # icao24, callsign, negara, t_pos, t_kontak, lon, lat, alt_baro, di_darat, kec, arah, lv, sensor, alt_geo, squawk, spi, sumber
        ["8a01af", "LNI890  ", "Indonesia", 1, 1, 107.1693, -6.3673, 5798.8, False, 204.1, 103.4, 10.4, None, 6164.6, "2415", False, 0],
        ["76b862", "TGW560  ", "Singapore", 1, 1, 105.8188, 1.4750, 8557.3, False, 213.7, 81.7, 3.6, None, 7825.7, None, False, 0],
        ["76b86c", "TGW116  ", "Singapore", 1, 1, 103.9958, 1.3591, None, True, 9.8, 202.5, None, None, None, None, False, 0],
        ["8a063a", "BTK7797 ", "Indonesia", 1, 1, 107.5825, -6.4493, 6568.4, False, 209.4, 90.4, -7.2, None, 6979.9, "2426", False, 0],
        ["abc123", "", "Indonesia", 1, 1, None, None, 1000.0, False, 100.0, 0.0, 0.0, None, None, None, False, 0],  # tanpa koordinat
        ["89647c", "UAE5CL  ", "United Arab Emirates", 1, 1, 100.0, 2.0, 11000.0, False, 250.0, 300.0, 0.1, None, 11200.0, None, False, 0],
    ],
}


@pytest.fixture
def bandara():
    return muat_data.muat_bandara()


@pytest.fixture
def df(bandara):
    return analisis.perkaya(opensky.states_ke_dataframe(PAYLOAD), bandara)


# ---------------------------------------------------------------- opensky
def test_states_ke_dataframe_membuang_baris_tanpa_koordinat():
    hasil = opensky.states_ke_dataframe(PAYLOAD)
    assert len(hasil) == 5
    assert "abc123" not in set(hasil["icao24"])


def test_states_ke_dataframe_membersihkan_callsign_dan_waktu():
    hasil = opensky.states_ke_dataframe(PAYLOAD)
    assert hasil.loc[0, "callsign"] == "LNI890"
    assert (hasil["waktu_snapshot"] == PAYLOAD["time"]).all()
    assert str(hasil["waktu"].dt.tz) == "UTC"
    assert "sensor" not in hasil.columns


def test_states_kosong_menghasilkan_dataframe_kosong_dengan_kolom():
    hasil = opensky.states_ke_dataframe({"time": 0, "states": None})
    assert hasil.empty
    assert "lat" in hasil.columns


def test_bbox_indonesia_masuk_akal():
    b = opensky.BBOX_INDONESIA
    assert b["lamin"] < -10 < 6 < b["lamax"]
    assert b["lomin"] < 95 < 141 < b["lomax"]


# ---------------------------------------------------------------- maskapai
@pytest.mark.parametrize(
    "callsign, harapan",
    [
        ("GIA412", "Garuda Indonesia"),
        ("LNI890", "Lion Air"),
        ("BTK7797", "Batik Air"),
        ("tgw560", "Scoot"),
        ("UAE5CL", "Emirates"),
        ("PK-LQH", maskapai.PENERBANGAN_UMUM),
        ("9VSHA", maskapai.PENERBANGAN_UMUM),
        ("ZZZ999", maskapai.TIDAK_DIKENAL),
        ("", maskapai.TIDAK_DIKENAL),
        (None, maskapai.TIDAK_DIKENAL),
    ],
)
def test_tebak_maskapai(callsign, harapan):
    assert maskapai.tebak_maskapai(callsign) == harapan


def test_prefix_dan_negara_maskapai():
    assert maskapai.prefix_callsign("CTV123") == "CTV"
    assert maskapai.prefix_callsign("PK-ABC") is None
    assert maskapai.negara_maskapai("SIA33") == "Singapura"
    assert maskapai.apakah_maskapai_indonesia("WON1234")
    assert not maskapai.apakah_maskapai_indonesia("QFA41")


def test_semua_kode_icao_tiga_huruf_kapital():
    for kode, (nama, negara) in maskapai.MASKAPAI.items():
        assert len(kode) == 3 and kode.isupper(), kode
        assert nama and negara


# ---------------------------------------------------------------- analisis
def test_haversine_cgk_dps_sekitar_983_km():
    assert analisis.haversine_km(-6.1256, 106.6559, -8.7482, 115.1672) == pytest.approx(983, abs=5)


def test_haversine_nol_dan_simetris():
    assert analisis.haversine_km(1, 2, 1, 2) == 0
    a = analisis.haversine_km(-6, 106, 1, 103)
    b = analisis.haversine_km(1, 103, -6, 106)
    assert a == pytest.approx(b)


def test_haversine_vektor_sama_dengan_skalar():
    lat = pd.Series([-6.2, 1.35, -8.7])
    lon = pd.Series([106.8, 103.8, 115.2])
    v = analisis.haversine_vektor(lat, lon, 0.0, 110.0)
    for i in range(3):
        assert v.iloc[i] == pytest.approx(analisis.haversine_km(lat[i], lon[i], 0.0, 110.0))


@pytest.mark.parametrize(
    "alt, lv, darat, harapan",
    [
        (11000, 0.1, False, "Jelajah"),
        (2000, 8.0, False, "Naik"),
        (1500, -6.0, False, "Turun"),
        (None, None, True, "Di darat"),
        (100, 0.0, False, "Di darat"),
        (None, None, False, "Tidak diketahui"),
    ],
)
def test_fase_terbang(alt, lv, darat, harapan):
    assert analisis.fase_terbang(alt, lv, darat) == harapan


def test_perkaya_menambah_kolom_turunan(df):
    for kol in ["maskapai", "negara_maskapai", "fase", "alt_kaki", "kecepatan_kmh", "bandara_terdekat", "jarak_bandara_km"]:
        assert kol in df.columns
    lni = df[df["callsign"] == "LNI890"].iloc[0]
    assert lni["maskapai"] == "Lion Air"
    assert lni["fase"] == "Naik"
    assert lni["alt_kaki"] == pytest.approx(5798.8 * 3.28084, abs=1)
    assert lni["bandara_terdekat"] in {"CGK", "HLP"}  # di atas Jakarta/Bekasi
    tgw = df[df["callsign"] == "TGW116"].iloc[0]
    assert tgw["fase"] == "Di darat"
    assert tgw["bandara_terdekat"] == "SIN"


def test_perkaya_dataframe_kosong_tidak_error(bandara):
    kosong = opensky.states_ke_dataframe({"time": 0, "states": []})
    hasil = analisis.perkaya(kosong, bandara)
    assert hasil.empty and "maskapai" in hasil.columns


def test_hitung_unik_tidak_menggandakan_jejak(df):
    jejak = pd.concat([df, df.assign(waktu_snapshot=df["waktu_snapshot"] + 20)], ignore_index=True)
    per_negara = analisis.hitung_unik(jejak, "negara_asal")
    assert per_negara.set_index("negara_asal").loc["Indonesia", "pesawat"] == 2
    assert per_negara.set_index("negara_asal").loc["Singapore", "pesawat"] == 2
    assert per_negara["persen"].sum() == pytest.approx(100, abs=0.5)


def test_ringkasan_kepemilikan(df):
    r = analisis.ringkasan_kepemilikan(df)
    assert r["total"] == 5
    assert r["indonesia"] == 2 and r["asing"] == 3
    assert r["persen_indonesia"] == 40.0
    assert r["negara_teratas"] in {"Indonesia", "Singapore"}  # seri 2-2, urutan bebas
    assert r["maskapai_teratas"] == "Scoot"


def test_ringkasan_kosong():
    r = analisis.ringkasan_kepemilikan(pd.DataFrame(columns=["icao24", "negara_asal", "maskapai"]))
    assert r["total"] == 0 and r["negara_teratas"] == "-"


def test_grid_kepadatan_mengelompokkan_titik_berdekatan(df):
    g = analisis.grid_kepadatan(df, ukuran_deg=1.0)
    # LNI890 (-6.37, 107.17) dan BTK7797 (-6.45, 107.58) jatuh di sel yang sama
    teratas = g.iloc[0]
    assert teratas["pesawat"] == 2 and teratas["titik"] == 2
    assert teratas["lat_tengah"] == -6.5 and teratas["lon_tengah"] == 107.5
    assert g["titik"].sum() == len(df)


def test_bandara_tersibuk_memakai_bandara_terdekat(df, bandara):
    sibuk = analisis.bandara_tersibuk(df, bandara, radius_km=60, alt_maks_m=3500)
    # Hanya TGW116 yang rendah (di darat, Changi). Batam tidak boleh ikut terhitung.
    assert list(sibuk["kode"]) == ["SIN"]
    assert sibuk.iloc[0]["pesawat"] == 1


def test_label_lokasi(bandara):
    assert analisis.label_lokasi(1.36, 103.99, bandara) == "Sekitar Singapura (SIN)"
    assert "km dari" in analisis.label_lokasi(-3.0, 110.0, bandara)


def test_panjang_jejak(df):
    geser = df.copy()
    geser["waktu_snapshot"] += 20
    geser["lat"] += 0.1  # sekitar 11 km ke utara
    jejak = pd.concat([df, geser], ignore_index=True)
    hasil = analisis.panjang_jejak_km(jejak)
    assert len(hasil) == 5
    assert (hasil["segmen"] == 1).all()
    assert hasil["km"].iloc[0] == pytest.approx(11.1, abs=0.2)


# ---------------------------------------------------------------- data & peta
def test_bandara_csv_valid(bandara):
    assert len(bandara) >= 30
    assert bandara["kode"].is_unique
    assert bandara["lat"].between(-12, 7).all() and bandara["lon"].between(94, 142).all()
    assert (bandara["negara"] == "Indonesia").sum() >= 25


def test_sampel_offline_bisa_dimuat():
    sampel = muat_data.muat_sampel()
    info = muat_data.info_sampel(sampel)
    assert info["snapshot"] >= 10
    assert info["pesawat"] >= 20
    terakhir = muat_data.snapshot_terakhir(sampel)
    assert terakhir["waktu_snapshot"].nunique() == 1
    assert sampel["lat"].between(-12, 7).all() and sampel["lon"].between(94, 142).all()


def test_peta_dibangun_tanpa_error(df, bandara):
    m = peta.peta_pesawat(df, bandara)
    html = m.get_root().render()
    assert "LNI890" in html and "arcgisonline" in html
    g = analisis.grid_kepadatan(df, 1.0).head(3)
    g["label"] = [analisis.label_lokasi(a, b, bandara) for a, b in zip(g["lat_tengah"], g["lon_tengah"])]
    m2 = peta.peta_heatmap(df, bandara, g)
    assert "HeatMap" in m2.get_root().render() or "heat" in m2.get_root().render().lower()


def test_warna_kelompok_negara():
    assert peta.kelompok_negara("Indonesia") == "Indonesia"
    assert peta.kelompok_negara("Hong Kong") == "Tiongkok & Hong Kong"
    assert peta.kelompok_negara("Peru") == peta.KELOMPOK_LAIN
    assert peta.warna_negara("Indonesia") == "#f2b705"
    assert peta.warna_negara(None) == peta.WARNA_KELOMPOK[peta.KELOMPOK_LAIN]
