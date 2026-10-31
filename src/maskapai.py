"""Menebak maskapai dari callsign ADS-B.

Callsign penerbangan berjadwal biasanya berbentuk ``<kode ICAO 3 huruf><nomor>``,
misalnya ``GIA412`` adalah Garuda Indonesia penerbangan 412. Kode ICAO berbeda
dengan kode IATA 2 huruf yang tercetak di tiket (GA, JT, QG).

Penerbangan umum, pesawat militer, atau helikopter sering memakai registrasi
sebagai callsign (misalnya ``PK-ABC``) sehingga tidak masuk daftar ini.
Daftar di bawah mencakup maskapai yang lazim melintasi ruang udara Indonesia.
"""

from __future__ import annotations

import re

# kode ICAO -> (nama maskapai, negara)
MASKAPAI: dict[str, tuple[str, str]] = {
    # Indonesia
    "GIA": ("Garuda Indonesia", "Indonesia"),
    "CTV": ("Citilink", "Indonesia"),
    "LNI": ("Lion Air", "Indonesia"),
    "BTK": ("Batik Air", "Indonesia"),
    "WON": ("Wings Air", "Indonesia"),
    "SJV": ("Super Air Jet", "Indonesia"),
    "SJY": ("Sriwijaya Air", "Indonesia"),
    "NAM": ("NAM Air", "Indonesia"),
    "AWQ": ("Indonesia AirAsia", "Indonesia"),
    "IDX": ("Indonesia AirAsia X", "Indonesia"),
    "TNU": ("TransNusa", "Indonesia"),
    "PAS": ("Pelita Air", "Indonesia"),
    "SQS": ("Susi Air", "Indonesia"),
    "TGN": ("Trigana Air", "Indonesia"),
    "MYU": ("My Indo Airlines", "Indonesia"),
    # Singapura
    "SIA": ("Singapore Airlines", "Singapura"),
    "TGW": ("Scoot", "Singapura"),
    "JSA": ("Jetstar Asia", "Singapura"),
    "SQC": ("Singapore Airlines Cargo", "Singapura"),
    # Malaysia
    "MAS": ("Malaysia Airlines", "Malaysia"),
    "AXM": ("AirAsia", "Malaysia"),
    "XAX": ("AirAsia X", "Malaysia"),
    "MXD": ("Batik Air Malaysia", "Malaysia"),
    "MHV": ("MASkargo", "Malaysia"),
    # Asia Tenggara lainnya
    "THA": ("Thai Airways", "Thailand"),
    "TAX": ("Thai AirAsia", "Thailand"),
    "TLM": ("Thai Lion Air", "Thailand"),
    "PAL": ("Philippine Airlines", "Filipina"),
    "CEB": ("Cebu Pacific", "Filipina"),
    "HVN": ("Vietnam Airlines", "Vietnam"),
    "VJC": ("VietJet Air", "Vietnam"),
    "RBA": ("Royal Brunei", "Brunei"),
    # Australia & Selandia Baru
    "QFA": ("Qantas", "Australia"),
    "JST": ("Jetstar", "Australia"),
    "VOZ": ("Virgin Australia", "Australia"),
    "ANZ": ("Air New Zealand", "Selandia Baru"),
    # Asia Timur
    "CPA": ("Cathay Pacific", "Hong Kong"),
    "CES": ("China Eastern", "Tiongkok"),
    "CSN": ("China Southern", "Tiongkok"),
    "CCA": ("Air China", "Tiongkok"),
    "CXA": ("Xiamen Air", "Tiongkok"),
    "CAL": ("China Airlines", "Taiwan"),
    "EVA": ("EVA Air", "Taiwan"),
    "KAL": ("Korean Air", "Korea Selatan"),
    "AAR": ("Asiana Airlines", "Korea Selatan"),
    "JAL": ("Japan Airlines", "Jepang"),
    "ANA": ("All Nippon Airways", "Jepang"),
    # Timur Tengah, Asia Selatan, Amerika
    "QTR": ("Qatar Airways", "Qatar"),
    "UAE": ("Emirates", "Uni Emirat Arab"),
    "ETD": ("Etihad Airways", "Uni Emirat Arab"),
    "SVA": ("Saudia", "Arab Saudi"),
    "THY": ("Turkish Airlines", "Turki"),
    "AIC": ("Air India", "India"),
    "UAL": ("United Airlines", "Amerika Serikat"),
    # Eropa
    "KLM": ("KLM", "Belanda"),
    "DLH": ("Lufthansa", "Jerman"),
    # Kargo
    "FDX": ("FedEx Express", "Amerika Serikat"),
    "UPS": ("UPS Airlines", "Amerika Serikat"),
    "GEC": ("Lufthansa Cargo", "Jerman"),
    "CLX": ("Cargolux", "Luksemburg"),
    "MPH": ("Martinair Cargo", "Belanda"),
}

TIDAK_DIKENAL = "Tidak dikenal"
PENERBANGAN_UMUM = "Registrasi / penerbangan umum"

_POLA_ICAO = re.compile(r"^([A-Z]{3})[0-9][0-9A-Z]{0,4}$")
_POLA_REGISTRASI = re.compile(r"^(PK|9V|9M|VH|RP|HS|VN|V8|JA|HL|A6|A7|N|B)[- ]?[A-Z0-9]{2,5}$")


def prefix_callsign(callsign: str | None) -> str | None:
    """Mengambil 3 huruf kode ICAO dari callsign, atau None jika pola tidak cocok.

    >>> prefix_callsign("GIA412")
    'GIA'
    >>> prefix_callsign("PK-ABC") is None
    True
    """
    if not callsign:
        return None
    cocok = _POLA_ICAO.match(callsign.strip().upper())
    return cocok.group(1) if cocok else None


def tebak_maskapai(callsign: str | None) -> str:
    """Nama maskapai dari callsign, atau kategori lain jika tidak dikenal.

    >>> tebak_maskapai("LNI890")
    'Lion Air'
    >>> tebak_maskapai("PK-LQH")
    'Registrasi / penerbangan umum'
    >>> tebak_maskapai("")
    'Tidak dikenal'
    """
    if not callsign or not callsign.strip():
        return TIDAK_DIKENAL
    cs = callsign.strip().upper()
    prefix = prefix_callsign(cs)
    if prefix and prefix in MASKAPAI:
        return MASKAPAI[prefix][0]
    if _POLA_REGISTRASI.match(cs):
        return PENERBANGAN_UMUM
    return TIDAK_DIKENAL


def negara_maskapai(callsign: str | None) -> str | None:
    """Negara asal maskapai berdasarkan callsign, None jika tidak dikenal."""
    prefix = prefix_callsign(callsign)
    if prefix and prefix in MASKAPAI:
        return MASKAPAI[prefix][1]
    return None


def apakah_maskapai_indonesia(callsign: str | None) -> bool:
    """True jika callsign milik maskapai Indonesia."""
    return negara_maskapai(callsign) == "Indonesia"
