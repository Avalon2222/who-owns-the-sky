"""Memuat data: bandara (CSV statis), sampel offline, atau data live (adsb.lol, cadangan OpenSky).

Prinsip: aplikasi tidak boleh gagal hanya karena internet mati atau sumber live
menolak. Karena itu setiap pemanggilan live memiliki cadangan sampel.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src import adsb, opensky

DIR_PROYEK = Path(__file__).resolve().parent.parent
DIR_DATA = DIR_PROYEK / "data"
FILE_BANDARA = DIR_DATA / "bandara.csv"
FILE_SAMPEL = DIR_DATA / "sample" / "snapshots.csv"

KOLOM_WAJIB = ["icao24", "callsign", "negara_asal", "lat", "lon", "waktu_snapshot"]


def muat_bandara(path: Path = FILE_BANDARA) -> pd.DataFrame:
    """Daftar bandara utama beserta koordinat (sumber: Wikipedia, dibulatkan 4 desimal)."""
    df = pd.read_csv(path)
    wajib = {"kode", "nama", "kota", "negara", "lat", "lon"}
    hilang = wajib - set(df.columns)
    if hilang:
        raise ValueError(f"Kolom bandara hilang: {sorted(hilang)}")
    df = df.dropna(subset=["lat", "lon"])
    df = df[df["lat"].between(-12, 7) & df["lon"].between(94, 142)]
    return df.reset_index(drop=True)


def muat_sampel(path: Path = FILE_SAMPEL) -> pd.DataFrame:
    """Sampel offline: gabungan banyak snapshot OpenSky yang sudah direkam ke CSV."""
    df = pd.read_csv(path, dtype={"icao24": str, "callsign": str, "squawk": str})
    hilang = set(KOLOM_WAJIB) - set(df.columns)
    if hilang:
        raise ValueError(f"Kolom sampel hilang: {sorted(hilang)}")
    df["callsign"] = df["callsign"].fillna("").astype(str).str.strip()
    df["di_darat"] = df["di_darat"].fillna(False).astype(bool)
    df["waktu"] = pd.to_datetime(df["waktu_snapshot"], unit="s", utc=True)
    return df.dropna(subset=["lat", "lon"]).reset_index(drop=True)


def info_sampel(df: pd.DataFrame) -> dict:
    """Ringkasan sampel untuk ditampilkan: jumlah snapshot, rentang waktu, pesawat unik."""
    if df.empty:
        return {"snapshot": 0, "mulai": None, "selesai": None, "pesawat": 0, "baris": 0}
    return {
        "snapshot": int(df["waktu_snapshot"].nunique()),
        "mulai": df["waktu"].min(),
        "selesai": df["waktu"].max(),
        "pesawat": int(df["icao24"].nunique()),
        "baris": int(len(df)),
    }


def snapshot_terakhir(df: pd.DataFrame) -> pd.DataFrame:
    """Hanya baris dari snapshot paling akhir (posisi "sekarang" dalam sampel)."""
    if df.empty:
        return df
    t = df["waktu_snapshot"].max()
    return df[df["waktu_snapshot"] == t].reset_index(drop=True)


def muat_live_atau_sampel() -> tuple[pd.DataFrame, str, str]:
    """Mencoba adsb.lol, lalu OpenSky; jika keduanya gagal, memakai sampel.

    Mengembalikan (DataFrame satu snapshot, sumber, pesan) dengan
    ``sumber`` bernilai "live" atau "sampel".
    """
    kesalahan: list[str] = []
    try:
        df, info = adsb.ambil_dataframe()
        if df.empty:
            raise adsb.AdsbError("adsb.lol mengembalikan 0 pesawat untuk kotak Indonesia.")
        catatan = "" if info["berhasil"] == info["total"] else f" ({info['berhasil']}/{info['total']} wilayah terjawab)"
        return df, "live", f"Data live adsb.lol, {len(df)} pesawat{catatan}."
    except adsb.AdsbError as exc:
        kesalahan.append(str(exc))
    try:
        df = opensky.ambil_dataframe()
        if df.empty:
            raise opensky.OpenSkyError("OpenSky mengembalikan 0 pesawat untuk kotak Indonesia.")
        return df, "live", f"Data live OpenSky, {len(df)} pesawat."
    except opensky.OpenSkyError as exc:
        kesalahan.append(str(exc))
    sampel = snapshot_terakhir(muat_sampel())
    return sampel, "sampel", " ".join(kesalahan) + " Menampilkan sampel offline."
