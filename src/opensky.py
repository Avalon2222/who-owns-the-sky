"""Pengambilan data ADS-B dari OpenSky Network (REST API, akses anonim).

Dokumentasi: https://openskynetwork.github.io/opensky-api/rest.html
Endpoint yang dipakai: GET /api/states/all dengan kotak batas (bounding box).

Catatan:
- Akses anonim dibatasi sekitar 400 kredit per hari. Kotak seluas Indonesia
  (lebih dari 400 derajat persegi) menghabiskan 4 kredit per permintaan, sehingga
  kira-kira 100 permintaan per hari. Aplikasi menyimpan hasil dalam cache 30 detik
  dan selalu punya cadangan berupa data sampel offline.
- Setiap "state vector" adalah daftar 17 kolom tanpa nama; fungsi di bawah
  memberi nama dan mengubahnya menjadi DataFrame.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import requests

URL_STATES = "https://opensky-network.org/api/states/all"

# Kotak batas Indonesia dengan sedikit margin: Sabang hingga Merauke,
# Pulau Rote hingga Miangas. Singapura dan Semenanjung Malaysia bagian selatan ikut masuk.
BBOX_INDONESIA: dict[str, float] = {
    "lamin": -11.5,
    "lomin": 94.5,
    "lamax": 6.5,
    "lomax": 141.5,
}

# Urutan kolom sesuai dokumentasi OpenSky (indeks 0 sampai 16).
KOLOM_STATE: list[str] = [
    "icao24",          # 0  alamat transponder 24-bit (heksadesimal)
    "callsign",        # 1  tanda panggil, 8 karakter, bisa kosong
    "negara_asal",     # 2  negara registrasi pesawat
    "waktu_posisi",    # 3  unix time posisi terakhir
    "waktu_kontak",    # 4  unix time kontak terakhir
    "lon",             # 5  bujur (derajat)
    "lat",             # 6  lintang (derajat)
    "alt_baro_m",      # 7  ketinggian barometrik (meter)
    "di_darat",        # 8  True jika di landasan
    "kecepatan_ms",    # 9  kecepatan terhadap tanah (m/s)
    "arah",            # 10 arah terbang searah jarum jam dari utara (derajat)
    "laju_vertikal",   # 11 laju naik/turun (m/s), positif = naik
    "sensor",          # 12 id sensor penerima (diabaikan)
    "alt_geo_m",       # 13 ketinggian geometrik (meter)
    "squawk",          # 14 kode transponder
    "spi",             # 15 special purpose indicator
    "sumber_posisi",   # 16 0 = ADS-B, 1 = ASTERIX, 2 = MLAT, 3 = FLARM
]


class OpenSkyError(RuntimeError):
    """Kesalahan ketika menghubungi OpenSky (jaringan, kuota, atau respons tidak valid)."""


def ambil_states(
    bbox: dict[str, float] | None = None,
    timeout: float = 20,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    """Memanggil endpoint /states/all dan mengembalikan JSON mentah.

    Mengembalikan dict dengan kunci ``time`` (unix time snapshot) dan ``states``
    (daftar state vector, bisa kosong). Melempar ``OpenSkyError`` bila gagal.
    """
    params = dict(bbox or BBOX_INDONESIA)
    klien = session or requests
    try:
        resp = klien.get(URL_STATES, params=params, timeout=timeout)
    except requests.RequestException as exc:  # jaringan putus, DNS, timeout
        raise OpenSkyError(f"Tidak dapat menghubungi OpenSky: {exc}") from exc

    if resp.status_code == 429:
        tunggu = resp.headers.get("X-Rate-Limit-Retry-After-Seconds", "?")
        raise OpenSkyError(f"Kuota OpenSky habis (HTTP 429). Coba lagi dalam {tunggu} detik.")
    if resp.status_code != 200:
        raise OpenSkyError(f"OpenSky menjawab HTTP {resp.status_code}.")

    try:
        data = resp.json()
    except ValueError as exc:
        raise OpenSkyError("Respons OpenSky bukan JSON yang valid.") from exc

    if not isinstance(data, dict) or "time" not in data:
        raise OpenSkyError("Struktur respons OpenSky tidak dikenali.")
    data["states"] = data.get("states") or []
    return data


def states_ke_dataframe(payload: dict[str, Any]) -> pd.DataFrame:
    """Mengubah JSON OpenSky menjadi DataFrame rapi, satu baris per pesawat.

    - Memberi nama 17 kolom, membuang kolom sensor.
    - Membersihkan callsign (spasi di kanan dihapus, kosong menjadi "").
    - Menambah kolom ``waktu_snapshot`` (unix time dari payload) dan
      ``waktu`` (Timestamp UTC) agar mudah digabung antar-snapshot.
    - Membuang baris tanpa koordinat.
    """
    states = payload.get("states") or []
    baris = []
    for s in states:
        s = list(s)[:17] + [None] * (17 - len(s))  # jaga-jaga jika kolom kurang
        baris.append(s)
    df = pd.DataFrame(baris, columns=KOLOM_STATE).drop(columns=["sensor"])

    df["callsign"] = df["callsign"].fillna("").astype(str).str.strip()
    df["waktu_snapshot"] = int(payload.get("time") or 0)
    df["waktu"] = pd.to_datetime(df["waktu_snapshot"], unit="s", utc=True)

    for kol in ["lon", "lat", "alt_baro_m", "kecepatan_ms", "arah", "laju_vertikal", "alt_geo_m"]:
        df[kol] = pd.to_numeric(df[kol], errors="coerce")
    df["di_darat"] = df["di_darat"].fillna(False).astype(bool)

    df = df.dropna(subset=["lat", "lon"]).reset_index(drop=True)
    return df


def ambil_dataframe(bbox: dict[str, float] | None = None, timeout: float = 20) -> pd.DataFrame:
    """Gabungan ``ambil_states`` + ``states_ke_dataframe`` untuk pemakaian sehari-hari."""
    return states_ke_dataframe(ambil_states(bbox=bbox, timeout=timeout))
