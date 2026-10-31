"""Merekam beberapa snapshot OpenSky ke CSV agar aplikasi bisa berjalan offline.

Contoh (dari folder proyek):
    python scripts/kumpulkan_sampel.py --jumlah 60 --jeda 20

Perintah di atas menarik data setiap 20 detik selama 20 menit (60 snapshot) dan
menulis ke data/sample/snapshots.csv. File lama akan ditimpa kecuali --tambah diberikan.

Perhatikan kuota anonim OpenSky (sekitar 100 permintaan per hari untuk kotak
seluas Indonesia). Skrip berhenti sendiri saat menerima HTTP 429.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import opensky  # noqa: E402
from src.muat_data import FILE_SAMPEL  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="Rekam snapshot OpenSky ke CSV.")
    p.add_argument("--jumlah", type=int, default=30, help="banyak snapshot (default 30)")
    p.add_argument("--jeda", type=int, default=20, help="jeda antar snapshot dalam detik (default 20)")
    p.add_argument("--keluaran", type=Path, default=FILE_SAMPEL, help="file CSV tujuan")
    p.add_argument("--tambah", action="store_true", help="tambahkan ke file yang sudah ada")
    args = p.parse_args()

    potongan: list[pd.DataFrame] = []
    if args.tambah and args.keluaran.exists():
        potongan.append(pd.read_csv(args.keluaran, dtype={"icao24": str, "callsign": str, "squawk": str}))

    for i in range(args.jumlah):
        mulai = time.time()
        try:
            df = opensky.ambil_dataframe()
            potongan.append(df.drop(columns=["waktu"]))
            print(f"[{i + 1}/{args.jumlah}] {len(df)} pesawat pada {df['waktu'].iloc[0] if len(df) else '-'}")
        except opensky.OpenSkyError as exc:
            print(f"[{i + 1}/{args.jumlah}] gagal: {exc}")
            if "429" in str(exc):
                break
        if i < args.jumlah - 1:
            time.sleep(max(0.0, args.jeda - (time.time() - mulai)))

    if not potongan:
        print("Tidak ada data yang terekam.")
        return 1

    hasil = pd.concat(potongan, ignore_index=True)
    args.keluaran.parent.mkdir(parents=True, exist_ok=True)
    hasil.to_csv(args.keluaran, index=False)
    print(f"Tersimpan: {args.keluaran} ({len(hasil)} baris, {hasil['waktu_snapshot'].nunique()} snapshot)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
