"""Perhitungan di atas DataFrame pesawat: fase terbang, kepemilikan, kepadatan, bandara.

Semua fungsi di sini murni pandas/Python tanpa Streamlit agar mudah diuji.
Istilah:
- "snapshot" = satu kali tarik data OpenSky (semua pesawat pada satu detik).
- "jejak" = gabungan banyak snapshot; satu pesawat muncul berkali-kali.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from src import maskapai as mk

R_BUMI_KM = 6371.0
KAKI_PER_METER = 3.28084


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Jarak great-circle (km) antara dua koordinat, bumi dianggap bola.

    >>> round(haversine_km(-6.1256, 106.6559, -8.7482, 115.1672))  # CGK ke DPS
    983
    """
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R_BUMI_KM * math.asin(math.sqrt(a))


def haversine_vektor(lat: pd.Series, lon: pd.Series, lat0: float, lon0: float) -> pd.Series:
    """Versi vektor dari ``haversine_km`` untuk satu titik acuan terhadap banyak titik."""
    p1 = np.radians(lat.to_numpy(dtype=float))
    p2 = math.radians(lat0)
    dp = p2 - p1
    dl = np.radians(lon0 - lon.to_numpy(dtype=float))
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * math.cos(p2) * np.sin(dl / 2) ** 2
    return pd.Series(2 * R_BUMI_KM * np.arcsin(np.sqrt(a)), index=lat.index)


def fase_terbang(alt_m: float | None, laju_vertikal: float | None, di_darat: bool) -> str:
    """Menebak fase penerbangan dari ketinggian dan laju vertikal.

    Ambang: |laju vertikal| > 2,5 m/s (sekitar 500 kaki/menit) dianggap naik/turun.
    Di bawah 300 m tanpa data lain dianggap "Di darat / rendah".

    >>> fase_terbang(11000, 0.1, False)
    'Jelajah'
    >>> fase_terbang(2000, 8.0, False)
    'Naik'
    >>> fase_terbang(1500, -6.0, False)
    'Turun'
    >>> fase_terbang(None, None, True)
    'Di darat'
    """
    if di_darat:
        return "Di darat"
    if alt_m is None or (isinstance(alt_m, float) and math.isnan(alt_m)):
        return "Tidak diketahui"
    lv = 0.0 if laju_vertikal is None or (isinstance(laju_vertikal, float) and math.isnan(laju_vertikal)) else laju_vertikal
    if alt_m < 300 and abs(lv) < 2.5:
        return "Di darat"
    if lv > 2.5:
        return "Naik"
    if lv < -2.5:
        return "Turun"
    return "Jelajah"


def bandara_terdekat(lat: float, lon: float, bandara: pd.DataFrame) -> tuple[str, float]:
    """Kode bandara terdekat dan jaraknya (km) dari sebuah titik."""
    jarak = haversine_vektor(bandara["lat"], bandara["lon"], lat, lon)
    i = jarak.idxmin()
    return str(bandara.loc[i, "kode"]), float(jarak.loc[i])


def perkaya(df: pd.DataFrame, bandara: pd.DataFrame | None = None) -> pd.DataFrame:
    """Menambah kolom turunan yang dipakai di seluruh aplikasi.

    Kolom baru: maskapai, negara_maskapai, fase, alt_kaki, kecepatan_kmh,
    bandara_terdekat, jarak_bandara_km (dua terakhir hanya bila ``bandara`` diberikan).
    """
    out = df.copy()
    if out.empty:
        for kol in ["maskapai", "negara_maskapai", "fase", "alt_kaki", "kecepatan_kmh",
                    "bandara_terdekat", "jarak_bandara_km"]:
            out[kol] = pd.Series(dtype="object")
        return out

    out["maskapai"] = out["callsign"].map(mk.tebak_maskapai)
    out["negara_maskapai"] = out["callsign"].map(mk.negara_maskapai).fillna(out["negara_asal"])
    out["fase"] = [
        fase_terbang(a, v, d)
        for a, v, d in zip(out["alt_baro_m"], out["laju_vertikal"], out["di_darat"])
    ]
    out["alt_kaki"] = (out["alt_baro_m"] * KAKI_PER_METER).round()
    out["kecepatan_kmh"] = (out["kecepatan_ms"] * 3.6).round()

    if bandara is not None and not bandara.empty:
        kode, jarak = [], []
        for lat, lon in zip(out["lat"], out["lon"]):
            k, j = bandara_terdekat(lat, lon, bandara)
            kode.append(k)
            jarak.append(round(j, 1))
        out["bandara_terdekat"] = kode
        out["jarak_bandara_km"] = jarak
    return out


def hitung_unik(df: pd.DataFrame, kolom: str, n: int | None = None) -> pd.DataFrame:
    """Jumlah pesawat unik (icao24) per nilai ``kolom``, urut menurun.

    Dipakai agar jejak (banyak snapshot) tidak menggandakan hitungan.
    Hasil: DataFrame dengan kolom [kolom, "pesawat", "persen"].
    """
    if df.empty:
        return pd.DataFrame(columns=[kolom, "pesawat", "persen"])
    s = df.groupby(kolom)["icao24"].nunique().sort_values(ascending=False)
    total = df["icao24"].nunique()
    hasil = s.reset_index().rename(columns={"icao24": "pesawat"})
    hasil["persen"] = (hasil["pesawat"] / max(total, 1) * 100).round(1)
    return hasil.head(n) if n else hasil


def ringkasan_kepemilikan(df: pd.DataFrame) -> dict:
    """Angka-angka ringkas untuk kartu KPI: siapa yang "memiliki" langit saat ini."""
    if df.empty:
        return {
            "total": 0, "indonesia": 0, "persen_indonesia": 0.0,
            "negara_teratas": "-", "maskapai_teratas": "-", "asing": 0,
            "jumlah_negara": 0,
        }
    total = df["icao24"].nunique()
    indo = df.loc[df["negara_asal"] == "Indonesia", "icao24"].nunique()
    negara = hitung_unik(df, "negara_asal")
    per_maskapai = hitung_unik(df[~df["maskapai"].isin([mk.TIDAK_DIKENAL, mk.PENERBANGAN_UMUM])], "maskapai")
    return {
        "total": int(total),
        "indonesia": int(indo),
        "asing": int(total - indo),
        "persen_indonesia": round(indo / total * 100, 1) if total else 0.0,
        "negara_teratas": str(negara.iloc[0, 0]) if not negara.empty else "-",
        "maskapai_teratas": str(per_maskapai.iloc[0, 0]) if not per_maskapai.empty else "-",
        "jumlah_negara": int(df["negara_asal"].nunique()),
    }


def grid_kepadatan(df: pd.DataFrame, ukuran_deg: float = 0.5) -> pd.DataFrame:
    """Membagi peta menjadi kotak ``ukuran_deg`` derajat dan menghitung isi tiap kotak.

    Hasil: [lat_tengah, lon_tengah, titik, pesawat], urut dari yang terpadat.
    ``titik`` = jumlah posisi (semua snapshot), ``pesawat`` = icao24 unik.
    Ukuran 0,5 derajat kira-kira 55 km di khatulistiwa.
    """
    if df.empty:
        return pd.DataFrame(columns=["lat_tengah", "lon_tengah", "titik", "pesawat"])
    g = df.copy()
    g["lat_sel"] = np.floor(g["lat"] / ukuran_deg).astype(int)
    g["lon_sel"] = np.floor(g["lon"] / ukuran_deg).astype(int)
    agg = (
        g.groupby(["lat_sel", "lon_sel"])
        .agg(titik=("icao24", "size"), pesawat=("icao24", "nunique"))
        .reset_index()
    )
    agg["lat_tengah"] = (agg["lat_sel"] + 0.5) * ukuran_deg
    agg["lon_tengah"] = (agg["lon_sel"] + 0.5) * ukuran_deg
    return (
        agg[["lat_tengah", "lon_tengah", "titik", "pesawat"]]
        .sort_values(["pesawat", "titik"], ascending=False)
        .reset_index(drop=True)
    )


def label_lokasi(lat: float, lon: float, bandara: pd.DataFrame) -> str:
    """Label ramah untuk sebuah koordinat: nama bandara terdekat beserta jaraknya."""
    kode, jarak = bandara_terdekat(lat, lon, bandara)
    baris = bandara.loc[bandara["kode"] == kode].iloc[0]
    if jarak < 40:
        return f"Sekitar {baris['kota']} ({kode})"
    return f"{jarak:.0f} km dari {baris['kota']} ({kode})"


def bandara_tersibuk(
    df: pd.DataFrame,
    bandara: pd.DataFrame,
    radius_km: float = 60,
    alt_maks_m: float = 3500,
) -> pd.DataFrame:
    """Jumlah pesawat unik yang rendah (< ``alt_maks_m``) di sekitar tiap bandara.

    Setiap posisi rendah hanya dihitung untuk bandara TERDEKAT-nya, dan hanya bila
    jaraknya <= ``radius_km``. Dengan begitu bandara yang bertetangga (Changi dan
    Hang Nadim hanya terpaut 30 km) tidak saling menggandakan hitungan.
    Pesawat rendah di dekat bandara hampir pasti sedang lepas landas atau mendarat.
    Hasil: [kode, nama, kota, negara, pesawat], hanya bandara dengan pesawat > 0.
    """
    kolom = ["kode", "nama", "kota", "negara", "pesawat"]
    if df.empty or bandara.empty:
        return pd.DataFrame(columns=kolom)
    rendah = df[(df["alt_baro_m"].fillna(0) < alt_maks_m) | df["di_darat"]].copy()
    if rendah.empty:
        return pd.DataFrame(columns=kolom)
    if "bandara_terdekat" not in rendah or "jarak_bandara_km" not in rendah:
        kode, jarak = [], []
        for lat, lon in zip(rendah["lat"], rendah["lon"]):
            k, j = bandara_terdekat(lat, lon, bandara)
            kode.append(k)
            jarak.append(j)
        rendah["bandara_terdekat"] = kode
        rendah["jarak_bandara_km"] = jarak
    dekat = rendah[rendah["jarak_bandara_km"] <= radius_km]
    hitung = dekat.groupby("bandara_terdekat")["icao24"].nunique()
    hasil = bandara[["kode", "nama", "kota", "negara"]].copy()
    hasil["pesawat"] = hasil["kode"].map(hitung).fillna(0).astype(int)
    return (
        hasil[hasil["pesawat"] > 0]
        .sort_values("pesawat", ascending=False)
        .reset_index(drop=True)
    )


def panjang_jejak_km(jejak: pd.DataFrame) -> pd.DataFrame:
    """Total jarak yang ditempuh tiap pesawat sepanjang jejak (menjumlahkan segmen).

    Hasil: [icao24, callsign, maskapai, segmen, km], urut dari yang terjauh.
    Hanya pesawat dengan minimal 2 posisi.
    """
    if jejak.empty:
        return pd.DataFrame(columns=["icao24", "callsign", "maskapai", "segmen", "km"])
    j = jejak.sort_values(["icao24", "waktu_snapshot"])
    hasil = []
    for icao, grup in j.groupby("icao24"):
        if len(grup) < 2:
            continue
        lat = grup["lat"].to_numpy()
        lon = grup["lon"].to_numpy()
        km = sum(haversine_km(lat[i], lon[i], lat[i + 1], lon[i + 1]) for i in range(len(lat) - 1))
        hasil.append({
            "icao24": icao,
            "callsign": grup["callsign"].iloc[-1],
            "maskapai": grup["maskapai"].iloc[-1] if "maskapai" in grup else "",
            "segmen": len(grup) - 1,
            "km": round(km, 1),
        })
    return (
        pd.DataFrame(hasil, columns=["icao24", "callsign", "maskapai", "segmen", "km"])
        .sort_values("km", ascending=False)
        .reset_index(drop=True)
    )
