"""Pengambilan data ADS-B dari adsb.lol (REST API publik, tanpa akun dan tanpa kunci).

Dokumentasi: https://api.adsb.lol/docs
Endpoint yang dipakai: GET /v2/lat/{lat}/lon/{lon}/dist/{dist} (radius dalam mil laut).

Mengapa adsb.lol:
- Gratis, tanpa pendaftaran, dan dapat dihubungi dari server Streamlit Community Cloud
  (OpenSky memblokir atau sangat lambat dari sana).
- Formatnya sama dengan readsb/tar1090, sehingga satu pesawat = satu dict bernama,
  tidak perlu menebak urutan kolom.

Catatan:
- Satu permintaan hanya mencakup satu lingkaran. Indonesia terlalu luas untuk satu
  lingkaran, jadi modul ini memanggil beberapa titik (``TITIK_CAKUPAN``), lalu
  menggabungkan hasilnya dan membuang duplikat berdasarkan alamat ICAO.
- Server membatasi laju permintaan (HTTP 429). Karena itu ada jeda antarpanggilan,
  dan lingkaran yang gagal cukup dilewati: lebih baik peta setengah terisi daripada
  kosong. Jika seluruh lingkaran gagal, ``AdsbError`` dilempar dan pemanggil jatuh
  ke sampel offline.
- adsb.lol tidak memberi kolom negara registrasi. Negara ditebak dari awalan
  registrasi (``PK-`` = Indonesia) dan, bila registrasi kosong, dari blok alamat ICAO 24-bit.
"""

from __future__ import annotations

import os
import time
from typing import Any

import pandas as pd
import requests

from src.opensky import BBOX_INDONESIA

URL_TITIK = "https://api.adsb.lol/v2/lat/{lat}/lon/{lon}/dist/{dist}"
HEADERS = {"User-Agent": "who-owns-the-sky (https://github.com/Avalon2222/who-owns-the-sky)"}
TIMEOUT = (5, 20)  # (sambung, baca) detik
RADIUS_NM = 1000   # radius tiap lingkaran, mil laut (sekitar 1.850 km; server menerima nilai ini)
JEDA_DETIK = 1.0   # jeda antarpanggilan agar tidak kena batas laju

# Pusat lingkaran pencarian (lat, lon). Dua lingkaran beradius 1.000 mil laut sudah
# menutup kotak batas Indonesia (Sabang sampai Merauke): barat berpusat di Sumatera
# selatan, timur di Maluku. Hasil di luar kotak batas dibuang saat dirapikan.
TITIK_CAKUPAN: list[tuple[float, float]] = [
    (-2.5, 103.0),
    (-2.5, 131.0),
]

KAKI_KE_METER = 0.3048
KNOT_KE_MS = 0.514444
KAKI_PER_MENIT_KE_MS = 0.00508

# Awalan registrasi -> negara (nama Inggris agar cocok dengan pengelompokan di src/peta.py
# dan dengan sampel OpenSky). Diurutkan otomatis dari yang terpanjang saat dicocokkan.
NEGARA_REGISTRASI: dict[str, str] = {
    "PK": "Indonesia", "9V": "Singapore", "9M": "Malaysia", "VH": "Australia", "ZK": "New Zealand",
    "B-H": "Hong Kong", "B-K": "Hong Kong", "B-L": "Hong Kong", "B-": "China",
    "A7": "Qatar", "A6": "United Arab Emirates", "HZ": "Saudi Arabia", "TC": "Turkey",
    "JA": "Japan", "HL": "South Korea", "HS": "Thailand", "RP": "Philippines", "VN": "Vietnam",
    "VT": "India", "N": "United States", "V8": "Brunei", "XU": "Cambodia", "4R": "Sri Lanka",
    "AP": "Pakistan", "S2": "Bangladesh", "9N": "Nepal", "RDPL": "Laos", "XY": "Myanmar",
    "P2": "Papua New Guinea", "DQ": "Fiji", "4K": "Azerbaijan",
    "PH": "Netherlands", "D-": "Germany", "F-": "France", "G-": "United Kingdom", "EC": "Spain",
    "I-": "Italy", "OE": "Austria", "HB": "Switzerland", "OO": "Belgium", "LN": "Norway",
    "SE": "Sweden", "OH": "Finland", "OY": "Denmark", "EI": "Ireland", "CS": "Portugal",
    "SP": "Poland", "OK": "Czech Republic", "HA": "Hungary", "LZ": "Bulgaria", "YR": "Romania",
    "SX": "Greece", "9H": "Malta", "OM": "Slovakia", "LX": "Luxembourg", "LY": "Lithuania",
    "RA": "Russia", "UK": "Uzbekistan", "UP": "Kazakhstan", "EP": "Iran", "4X": "Israel",
    "SU": "Egypt", "ET": "Ethiopia", "ZS": "South Africa", "5Y": "Kenya", "A9C": "Bahrain",
    "9K": "Kuwait", "A4O": "Oman", "JY": "Jordan", "OD": "Lebanon", "YK": "Syria",
    "C-": "Canada", "CF": "Canada", "XA": "Mexico", "XB": "Mexico", "XC": "Mexico",
    "PP": "Brazil", "PR": "Brazil", "PT": "Brazil", "PU": "Brazil", "LV": "Argentina", "CC": "Chile",
    "HK": "Colombia", "T7": "San Marino", "M-": "Isle of Man", "2-": "Guernsey",
    "VP-B": "Bermuda", "VQ-B": "Bermuda", "VP-C": "Cayman Islands", "P4": "Aruba",
}
_AWALAN_URUT = sorted(NEGARA_REGISTRASI, key=len, reverse=True)

# Blok alamat ICAO 24-bit (awal, akhir, negara) untuk pesawat tanpa registrasi di payload.
BLOK_ICAO: list[tuple[int, int, str]] = [
    (0x8A0000, 0x8A7FFF, "Indonesia"),
    (0x76C000, 0x76CFFF, "Singapore"),
    (0x750000, 0x757FFF, "Malaysia"),
    (0x7C0000, 0x7FFFFF, "Australia"),
    (0xC80000, 0xC87FFF, "New Zealand"),
    (0x780000, 0x7BFFFF, "China"),
    (0xA00000, 0xAFFFFF, "United States"),
    (0x840000, 0x87FFFF, "Japan"),
    (0x718000, 0x71FFFF, "South Korea"),
    (0x880000, 0x887FFF, "Thailand"),
    (0x758000, 0x75BFFF, "Philippines"),
    (0x888000, 0x88FFFF, "Vietnam"),
    (0x800000, 0x83FFFF, "India"),
    (0x896000, 0x896FFF, "United Arab Emirates"),
    (0x06A000, 0x06AFFF, "Qatar"),
    (0x710000, 0x717FFF, "Saudi Arabia"),
    (0x4B8000, 0x4BFFFF, "Turkey"),
    (0x895000, 0x8953FF, "Brunei"),
    (0xC00000, 0xC3FFFF, "Canada"),
    (0x3C0000, 0x3FFFFF, "Germany"),
    (0x380000, 0x3BFFFF, "France"),
    (0x400000, 0x43FFFF, "United Kingdom"),
    (0x340000, 0x37FFFF, "Spain"),
    (0x300000, 0x33FFFF, "Italy"),
    (0x480000, 0x487FFF, "Netherlands"),
    (0x100000, 0x1FFFFF, "Russia"),
    (0x0D0000, 0x0D7FFF, "Mexico"),
    (0xE40000, 0xE7FFFF, "Brazil"),
]
NEGARA_TIDAK_DIKETAHUI = "Tidak diketahui"

# Urutan kolom disamakan dengan src/opensky.py agar analisis dan peta tidak perlu tahu sumbernya.
KOLOM: list[str] = [
    "icao24", "callsign", "negara_asal", "waktu_posisi", "waktu_kontak", "lon", "lat", "alt_baro_m",
    "di_darat", "kecepatan_ms", "arah", "laju_vertikal", "alt_geo_m", "squawk", "spi", "sumber_posisi",
]


class AdsbError(RuntimeError):
    """Kesalahan ketika seluruh permintaan ke adsb.lol gagal."""


def negara_registrasi(registrasi: str | None, icao24: str | None = None) -> str:
    """Negara dari awalan registrasi (``PK-GPW`` -> Indonesia); cadangan: blok alamat ICAO."""
    reg = (registrasi or "").strip().upper()
    if reg:
        for awalan in _AWALAN_URUT:
            if reg.startswith(awalan):
                return NEGARA_REGISTRASI[awalan]
    if icao24:
        try:
            nilai = int(icao24, 16)
        except ValueError:
            return NEGARA_TIDAK_DIKETAHUI
        for awal, akhir, negara in BLOK_ICAO:
            if awal <= nilai <= akhir:
                return negara
    return NEGARA_TIDAK_DIKETAHUI


def _sumber_posisi(tipe: str | None) -> int:
    """Kode sumber posisi mengikuti konvensi OpenSky: 0 ADS-B, 1 ASTERIX/TIS-B, 2 MLAT."""
    t = (tipe or "").lower()
    if t.startswith("mlat"):
        return 2
    if t.startswith("tisb"):
        return 1
    return 0


def ambil_titik(
    lat: float,
    lon: float,
    dist: int = RADIUS_NM,
    timeout: float | tuple[float, float] = TIMEOUT,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    """Satu permintaan ke adsb.lol untuk lingkaran berpusat (lat, lon). Melempar ``AdsbError`` bila gagal."""
    klien = session or requests
    url = URL_TITIK.format(lat=lat, lon=lon, dist=dist)
    try:
        resp = klien.get(url, timeout=timeout, headers=HEADERS)
    except requests.RequestException as exc:
        raise AdsbError(f"Tidak dapat menghubungi adsb.lol: {exc}") from exc
    if resp.status_code == 429:
        raise AdsbError("adsb.lol membatasi laju permintaan (HTTP 429).")
    if resp.status_code != 200:
        raise AdsbError(f"adsb.lol menjawab HTTP {resp.status_code}.")
    try:
        data = resp.json()
    except ValueError as exc:
        raise AdsbError("Respons adsb.lol bukan JSON yang valid.") from exc
    if not isinstance(data, dict) or "ac" not in data:
        raise AdsbError("Struktur respons adsb.lol tidak dikenali.")
    data["ac"] = data.get("ac") or []
    return data


def ambil_semua(
    titik: list[tuple[float, float]] | None = None,
    jeda: float = JEDA_DETIK,
    session: requests.Session | None = None,
) -> tuple[list[dict[str, Any]], int, dict[str, int]]:
    """Memanggil semua lingkaran, menggabungkan pesawat (unik per alamat ICAO).

    Mengembalikan (daftar pesawat, waktu snapshot unix, info) dengan ``info`` berisi
    jumlah lingkaran yang berhasil dan total. Melempar ``AdsbError`` bila tak satu pun berhasil.
    """
    titik = titik or TITIK_CAKUPAN
    semua: dict[str, dict[str, Any]] = {}
    waktu_ms = 0
    berhasil = 0
    kesalahan: list[str] = []
    for i, (lat, lon) in enumerate(titik):
        if i and jeda:
            time.sleep(jeda)
        try:
            data = ambil_titik(lat, lon, session=session)
        except AdsbError as exc:
            kesalahan.append(str(exc))
            continue
        berhasil += 1
        waktu_ms = max(waktu_ms, int(data.get("now") or 0))
        for ac in data["ac"]:
            hexid = str(ac.get("hex") or "").lower()
            if hexid and hexid not in semua:
                semua[hexid] = ac
    if not berhasil:
        pesan = kesalahan[0] if kesalahan else "tidak ada lingkaran yang dipanggil"
        raise AdsbError(f"Semua {len(titik)} permintaan ke adsb.lol gagal: {pesan}")
    waktu = int(waktu_ms / 1000) if waktu_ms else int(time.time())
    return list(semua.values()), waktu, {"berhasil": berhasil, "total": len(titik)}


def ac_ke_dataframe(daftar: list[dict[str, Any]], waktu_snapshot: int,
                    bbox: dict[str, float] | None = None) -> pd.DataFrame:
    """Mengubah daftar pesawat adsb.lol menjadi DataFrame berkolom sama dengan ``opensky.states_ke_dataframe``.

    - Kaki -> meter, knot -> m/s, kaki/menit -> m/s.
    - ``alt_baro == "ground"`` berarti pesawat di darat (ketinggian barometrik dikosongkan).
    - Baris tanpa koordinat atau di luar kotak batas Indonesia dibuang.
    """
    bbox = bbox or BBOX_INDONESIA
    baris = []
    for ac in daftar:
        lat, lon = ac.get("lat"), ac.get("lon")
        if lat is None or lon is None:
            continue
        alt_baro = ac.get("alt_baro")
        di_darat = alt_baro == "ground"
        alt_baro_m = None if di_darat or not isinstance(alt_baro, (int, float)) else alt_baro * KAKI_KE_METER
        alt_geom = ac.get("alt_geom")
        alt_geo_m = alt_geom * KAKI_KE_METER if isinstance(alt_geom, (int, float)) else None
        gs = ac.get("gs")
        rate = ac.get("baro_rate", ac.get("geom_rate"))
        seen = ac.get("seen") or 0
        seen_pos = ac.get("seen_pos", seen) or 0
        icao24 = str(ac.get("hex") or "").lower()
        baris.append({
            "icao24": icao24,
            "callsign": str(ac.get("flight") or "").strip(),
            "negara_asal": negara_registrasi(ac.get("r"), icao24),
            "waktu_posisi": int(waktu_snapshot - float(seen_pos)),
            "waktu_kontak": int(waktu_snapshot - float(seen)),
            "lon": float(lon),
            "lat": float(lat),
            "alt_baro_m": alt_baro_m,
            "di_darat": bool(di_darat),
            "kecepatan_ms": gs * KNOT_KE_MS if isinstance(gs, (int, float)) else None,
            "arah": ac.get("track"),
            "laju_vertikal": rate * KAKI_PER_MENIT_KE_MS if isinstance(rate, (int, float)) else None,
            "alt_geo_m": alt_geo_m,
            "squawk": ac.get("squawk"),
            "spi": bool(ac.get("spi")),
            "sumber_posisi": _sumber_posisi(ac.get("type")),
        })
    df = pd.DataFrame(baris, columns=KOLOM)
    for kol in ["lon", "lat", "alt_baro_m", "kecepatan_ms", "arah", "laju_vertikal", "alt_geo_m"]:
        df[kol] = pd.to_numeric(df[kol], errors="coerce")
    df["di_darat"] = df["di_darat"].astype(bool)
    df["waktu_snapshot"] = int(waktu_snapshot)
    df["waktu"] = pd.to_datetime(df["waktu_snapshot"], unit="s", utc=True)
    df = df[df["lat"].between(bbox["lamin"], bbox["lamax"]) & df["lon"].between(bbox["lomin"], bbox["lomax"])]
    return df.reset_index(drop=True)


def ambil_dataframe(session: requests.Session | None = None) -> tuple[pd.DataFrame, dict[str, int]]:
    """Gabungan ``ambil_semua`` + ``ac_ke_dataframe`` untuk pemakaian sehari-hari."""
    daftar, waktu, info = ambil_semua(session=session)
    return ac_ke_dataframe(daftar, waktu), info


if __name__ == "__main__":  # pemeriksaan cepat dari terminal: python -m src.adsb
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    df, info = ambil_dataframe()
    print(f"{len(df)} pesawat dari {info['berhasil']}/{info['total']} lingkaran")
    print(df[["icao24", "callsign", "negara_asal", "lat", "lon", "alt_baro_m"]].head(10).to_string())
