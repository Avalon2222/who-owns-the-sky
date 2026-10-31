"""Membangun peta Folium: posisi pesawat (ikon berputar sesuai arah) dan heatmap jejak."""

from __future__ import annotations

import html

import folium
import pandas as pd
from folium.plugins import HeatMap

PUSAT_INDONESIA = (-2.5, 118.0)
ZOOM_AWAL = 5
TILE_GELAP = (
    "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/"
    "MapServer/tile/{z}/{y}/{x}"
)
ATRIBUSI_TILE = "Tiles &copy; Esri &mdash; Esri, HERE, Garmin, OpenStreetMap contributors"

# Negara registrasi dikelompokkan agar legenda tetap pendek (7 warna).
KELOMPOK_NEGARA: dict[str, str] = {
    "Indonesia": "Indonesia",
    "Singapore": "Singapura",
    "Malaysia": "Malaysia",
    "Australia": "Australia & Selandia Baru",
    "New Zealand": "Australia & Selandia Baru",
    "China": "Tiongkok & Hong Kong",
    "Hong Kong": "Tiongkok & Hong Kong",
    "Qatar": "Timur Tengah",
    "United Arab Emirates": "Timur Tengah",
    "Saudi Arabia": "Timur Tengah",
    "Turkey": "Timur Tengah",
}
KELOMPOK_LAIN = "Lainnya"

# Warna per kelompok. Indonesia sengaja paling mencolok (emas).
WARNA_KELOMPOK: dict[str, str] = {
    "Indonesia": "#f2b705",
    "Singapura": "#ff4d6d",
    "Malaysia": "#4cc9f0",
    "Australia & Selandia Baru": "#80ed99",
    "Tiongkok & Hong Kong": "#ff8c42",
    "Timur Tengah": "#c77dff",
    KELOMPOK_LAIN: "#9aa5b1",
}

# Ikon pesawat (jalur SVG 24x24, hidung menghadap ke atas = utara).
_JALUR_PESAWAT = (
    "M21 16v-2l-8-5V3.5c0-.83-.67-1.5-1.5-1.5S10 2.67 10 3.5V9l-8 5v2l8-2.5V19"
    "l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5l8 2.5z"
)


def kelompok_negara(negara: str | None) -> str:
    """Nama kelompok legenda untuk sebuah negara registrasi (OpenSky memakai nama Inggris)."""
    return KELOMPOK_NEGARA.get(negara or "", KELOMPOK_LAIN)


def warna_negara(negara: str | None) -> str:
    """Warna heksadesimal untuk negara registrasi, lewat kelompoknya."""
    return WARNA_KELOMPOK[kelompok_negara(negara)]


def ikon_pesawat(warna: str, arah: float | None, ukuran: int = 22) -> folium.DivIcon:
    """DivIcon berisi SVG pesawat yang diputar sebesar ``arah`` derajat searah jarum jam."""
    sudut = 0 if arah is None or pd.isna(arah) else float(arah)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{ukuran}" height="{ukuran}" viewBox="0 0 24 24" '
        f'style="transform: rotate({sudut:.0f}deg); filter: drop-shadow(0 0 2px #000);">'
        f'<path d="{_JALUR_PESAWAT}" fill="{warna}" stroke="#111" stroke-width="0.6"/></svg>'
    )
    return folium.DivIcon(html=svg, icon_size=(ukuran, ukuran), icon_anchor=(ukuran // 2, ukuran // 2))


def _teks(v, satuan: str = "", desimal: int = 0) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "-"
    return f"{v:,.{desimal}f}{satuan}"


def popup_pesawat(b: pd.Series) -> str:
    """HTML popup untuk satu baris pesawat."""
    callsign = html.escape(b.get("callsign") or "(tanpa callsign)")
    maskapai = html.escape(str(b.get("maskapai", "")))
    negara = html.escape(str(b.get("negara_asal", "")))
    fase = html.escape(str(b.get("fase", "")))
    bandara = b.get("bandara_terdekat")
    baris_bandara = (
        f"<tr><td>Bandara terdekat</td><td>{html.escape(str(bandara))} ({_teks(b.get('jarak_bandara_km'), ' km')})</td></tr>"
        if bandara else ""
    )
    return f"""
    <div style="font-family: system-ui, sans-serif; font-size: 13px; min-width: 220px;">
      <div style="font-size: 16px; font-weight: 700;">{callsign}</div>
      <div style="color:#555; margin-bottom:6px;">{maskapai} · {negara}</div>
      <table style="border-collapse: collapse; width:100%;">
        <tr><td>ICAO24</td><td><code>{html.escape(str(b.get('icao24', '')))}</code></td></tr>
        <tr><td>Fase</td><td>{fase}</td></tr>
        <tr><td>Ketinggian</td><td>{_teks(b.get('alt_baro_m'), ' m')} ({_teks(b.get('alt_kaki'), ' kaki')})</td></tr>
        <tr><td>Kecepatan</td><td>{_teks(b.get('kecepatan_kmh'), ' km/jam')}</td></tr>
        <tr><td>Arah</td><td>{_teks(b.get('arah'), '°')}</td></tr>
        <tr><td>Laju vertikal</td><td>{_teks(b.get('laju_vertikal'), ' m/s', 1)}</td></tr>
        {baris_bandara}
      </table>
    </div>
    """


def peta_dasar(pusat=PUSAT_INDONESIA, zoom: int = ZOOM_AWAL) -> folium.Map:
    """Peta gelap (Esri World Dark Gray) agar ikon berwarna terlihat jelas."""
    m = folium.Map(location=pusat, zoom_start=zoom, tiles=None, control_scale=True)
    folium.TileLayer(
        tiles=TILE_GELAP, attr=ATRIBUSI_TILE, name="Peta dasar gelap", control=False, max_zoom=16,
    ).add_to(m)
    return m


def tambah_bandara(m: folium.Map, bandara: pd.DataFrame, nama_lapisan: str = "Bandara") -> None:
    """Lingkaran kecil putih untuk setiap bandara, dalam satu FeatureGroup."""
    fg = folium.FeatureGroup(name=nama_lapisan, show=True)
    for _, b in bandara.iterrows():
        folium.CircleMarker(
            location=(b["lat"], b["lon"]),
            radius=4,
            color="#ffffff",
            weight=1,
            fill=True,
            fill_color="#ffffff",
            fill_opacity=0.8,
            tooltip=f"{b['kode']} · {b['nama']} ({b['kota']})",
        ).add_to(fg)
    fg.add_to(m)


def peta_pesawat(
    df: pd.DataFrame,
    bandara: pd.DataFrame | None = None,
    pusat=PUSAT_INDONESIA,
    zoom: int = ZOOM_AWAL,
) -> folium.Map:
    """Peta dengan satu ikon per pesawat, diwarnai per negara dan diputar sesuai arah."""
    m = peta_dasar(pusat, zoom)
    if bandara is not None and not bandara.empty:
        tambah_bandara(m, bandara)

    fg_indo = folium.FeatureGroup(name="Pesawat registrasi Indonesia", show=True)
    fg_asing = folium.FeatureGroup(name="Pesawat registrasi asing", show=True)
    for _, b in df.iterrows():
        warna = warna_negara(b.get("negara_asal"))
        marker = folium.Marker(
            location=(b["lat"], b["lon"]),
            icon=ikon_pesawat(warna, b.get("arah")),
            tooltip=f"{b.get('callsign') or b.get('icao24')} · {b.get('maskapai', '')}",
            popup=folium.Popup(popup_pesawat(b), max_width=320),
        )
        marker.add_to(fg_indo if b.get("negara_asal") == "Indonesia" else fg_asing)
    fg_indo.add_to(m)
    fg_asing.add_to(m)
    folium.LayerControl(collapsed=True).add_to(m)
    return m


def peta_heatmap(
    jejak: pd.DataFrame,
    bandara: pd.DataFrame | None = None,
    sel_terpadat: pd.DataFrame | None = None,
    radius: int = 14,
    blur: int = 18,
    pusat=PUSAT_INDONESIA,
    zoom: int = ZOOM_AWAL,
) -> folium.Map:
    """Heatmap dari seluruh posisi dalam jejak; opsional lingkaran untuk sel terpadat."""
    m = peta_dasar(pusat, zoom)
    if bandara is not None and not bandara.empty:
        tambah_bandara(m, bandara)

    titik = jejak[["lat", "lon"]].dropna().to_numpy().tolist()
    if titik:
        HeatMap(
            titik,
            name="Kepadatan jejak",
            radius=radius,
            blur=blur,
            min_opacity=0.25,
            gradient={"0.2": "#1d3557", "0.45": "#4cc9f0", "0.7": "#f2b705", "1": "#ff4d6d"},
        ).add_to(m)

    if sel_terpadat is not None and not sel_terpadat.empty:
        fg = folium.FeatureGroup(name="Sel terpadat", show=True)
        for i, s in sel_terpadat.reset_index(drop=True).iterrows():
            folium.CircleMarker(
                location=(s["lat_tengah"], s["lon_tengah"]),
                radius=10 + 2 * (len(sel_terpadat) - i),
                color="#ff4d6d",
                weight=2,
                fill=False,
                tooltip=f"#{i + 1}: {int(s['pesawat'])} pesawat, {int(s['titik'])} posisi"
                + (f" · {s['label']}" if "label" in s else ""),
            ).add_to(fg)
        fg.add_to(m)

    folium.LayerControl(collapsed=True).add_to(m)
    return m
