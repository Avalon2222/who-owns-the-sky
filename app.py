"""Who Owns the Sky? — peta pesawat di atas Indonesia dari data ADS-B publik (OpenSky).

Jalankan: streamlit run app.py
Struktur file ini dibaca dari atas ke bawah: konfigurasi → data → sidebar → KPI → tab.
"""

from __future__ import annotations

import os
from datetime import timezone, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from streamlit_folium import st_folium

from src import analisis, muat_data, opensky, peta
from src import maskapai as mk

# ------------------------------------------------------------------ konfigurasi
st.set_page_config(page_title="Who Owns the Sky?", page_icon="✈️", layout="wide")

# Kredensial OpenSky (opsional). Di Streamlit Community Cloud diisi lewat menu Secrets:
#   [opensky]
#   client_id = "..."
#   client_secret = "..."
# Tanpa kredensial, aplikasi memakai akses anonim lalu jatuh ke sampel bila kuota habis.
try:
    _opensky = st.secrets.get("opensky", {})
    for _kunci in ("client_id", "client_secret"):
        if _opensky.get(_kunci):
            os.environ.setdefault(f"OPENSKY_{_kunci.upper()}", str(_opensky[_kunci]))
except Exception:  # tidak ada berkas secrets: akses anonim
    pass

WIB = timezone(timedelta(hours=7))
EMAS = "#f2b705"
ABU = "#6c7a89"
TEMPLATE = "plotly_dark"
MAKS_SNAPSHOT_SESI = 120  # batas jejak yang disimpan di memori saat mode live


def fmt_wib(ts) -> str:
    """Timestamp UTC → teks WIB, misalnya '01 Nov 2026 01:05 WIB'."""
    if ts is None or pd.isna(ts):
        return "-"
    return pd.Timestamp(ts).tz_convert(WIB).strftime("%d %b %Y %H:%M:%S WIB")


def grafik_batang(df: pd.DataFrame, x: str, y: str, judul: str, sorot: str | None = None, hover=None) -> go.Figure:
    """Batang horizontal satu warna; satu kategori (misalnya Indonesia) bisa disorot emas."""
    warna = [EMAS if v == sorot else ABU for v in df[y]] if sorot else EMAS
    fig = go.Figure(
        go.Bar(
            x=df[x], y=df[y], orientation="h",
            marker_color=warna, marker_line_width=0,
            text=df[x], textposition="outside", cliponaxis=False,
            customdata=df[hover] if hover else None,
            hovertemplate="<b>%{y}</b><br>%{x} pesawat" + ("<br>%{customdata}%" if hover else "") + "<extra></extra>",
        )
    )
    fig.update_layout(
        template=TEMPLATE, title=judul, height=max(300, 28 * len(df) + 90),
        margin=dict(l=10, r=40, t=50, b=10), yaxis=dict(autorange="reversed", title=""),
        xaxis=dict(title="pesawat unik", showgrid=True, gridcolor="#223"),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


# ------------------------------------------------------------------ data
@st.cache_data(show_spinner=False)
def bandara_df() -> pd.DataFrame:
    return muat_data.muat_bandara()


@st.cache_data(show_spinner=False)
def sampel_df() -> pd.DataFrame:
    return analisis.perkaya(muat_data.muat_sampel(), bandara_df())


@st.cache_data(ttl=30, show_spinner=False)
def live_df() -> tuple[pd.DataFrame, str, str]:
    """Snapshot live (cache 30 detik agar kuota OpenSky awet). Jatuh ke sampel bila gagal."""
    df, sumber, pesan = muat_data.muat_live_atau_sampel()
    return analisis.perkaya(df, bandara_df()), sumber, pesan


def tambah_ke_jejak_sesi(snapshot: pd.DataFrame) -> pd.DataFrame:
    """Mode live: kumpulkan snapshot yang pernah dilihat agar heatmap punya jejak."""
    jejak = st.session_state.get("jejak_live")
    if jejak is None or jejak.empty:
        jejak = snapshot
    elif snapshot["waktu_snapshot"].iloc[0] not in set(jejak["waktu_snapshot"].unique()):
        jejak = pd.concat([jejak, snapshot], ignore_index=True)
        waktu = sorted(jejak["waktu_snapshot"].unique())
        if len(waktu) > MAKS_SNAPSHOT_SESI:
            jejak = jejak[jejak["waktu_snapshot"].isin(waktu[-MAKS_SNAPSHOT_SESI:])]
    st.session_state["jejak_live"] = jejak
    return jejak


# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.title("✈️ Who Owns the Sky?")
    st.caption("Setiap pesawat meninggalkan jejak.")

    sumber_pilihan = st.radio(
        "Sumber data",
        ["Live (OpenSky)", "Sampel offline"],
        help="Live menarik data ADS-B terbaru dari OpenSky Network (gratis; anonim bila tanpa akun, kuota terbatas). "
             "Sampel offline adalah rekaman beberapa snapshot yang disertakan dalam repositori.",
    )
    kol_a, kol_b = st.columns(2)
    if kol_a.button("🔄 Segarkan", use_container_width=True, help="Tarik snapshot baru (cache 30 detik)."):
        live_df.clear()
    if kol_b.button("🧹 Hapus jejak", use_container_width=True, help="Kosongkan jejak yang terkumpul di mode live."):
        st.session_state.pop("jejak_live", None)

    bandara = bandara_df()
    if sumber_pilihan.startswith("Live"):
        terkini, sumber, pesan = live_df()
        if sumber == "live":
            jejak = tambah_ke_jejak_sesi(terkini)
        else:
            jejak = sampel_df()
            terkini = muat_data.snapshot_terakhir(jejak)
    else:
        jejak = sampel_df()
        terkini = muat_data.snapshot_terakhir(jejak)
        sumber, pesan = "sampel", "Sampel offline dari repositori."

    st.divider()
    st.subheader("Filter")
    negara_opsi = sorted(terkini["negara_asal"].dropna().unique().tolist())
    negara_pilih = st.multiselect("Negara registrasi", negara_opsi, default=[])
    maskapai_opsi = analisis.hitung_unik(terkini, "maskapai")["maskapai"].tolist()
    maskapai_pilih = st.multiselect("Maskapai", maskapai_opsi, default=[])
    sembunyikan_darat = st.checkbox("Sembunyikan pesawat di darat", value=False)
    alt_maks = int(max(45000, (terkini["alt_kaki"].max() if terkini["alt_kaki"].notna().any() else 45000)))
    rentang_alt = st.slider("Ketinggian (kaki)", 0, alt_maks, (0, alt_maks), step=1000)

    st.divider()
    mode_belajar = st.toggle("🎓 Mode belajar", value=False, help="Tampilkan penjelasan konsep di setiap bagian.")
    st.caption(
        "Data: [OpenSky Network](https://opensky-network.org) · peta dasar Esri. "
        "Posisi pesawat berasal dari penerima sukarelawan, sehingga cakupan di Indonesia timur tipis."
    )


def terapkan_filter(df: pd.DataFrame) -> pd.DataFrame:
    hasil = df
    if negara_pilih:
        hasil = hasil[hasil["negara_asal"].isin(negara_pilih)]
    if maskapai_pilih:
        hasil = hasil[hasil["maskapai"].isin(maskapai_pilih)]
    if sembunyikan_darat:
        hasil = hasil[~hasil["di_darat"] & (hasil["fase"] != "Di darat")]
    lo, hi = rentang_alt
    if (lo, hi) != (0, alt_maks):
        alt = hasil["alt_kaki"].fillna(0)
        hasil = hasil[alt.between(lo, hi)]
    return hasil


terkini_f = terapkan_filter(terkini)
jejak_f = terapkan_filter(jejak)

# ------------------------------------------------------------------ judul & KPI
st.title("Who Owns the Sky?")
st.markdown(
    "Siapa yang menguasai ruang udara Indonesia **saat ini**? Setiap ikon adalah satu pesawat yang "
    "memancarkan sinyal ADS-B dan tertangkap penerima publik OpenSky Network. "
    "Warna menunjukkan negara registrasi, arah ikon mengikuti arah terbang."
)

if sumber == "live":
    st.success(f"🟢 {pesan} Snapshot {fmt_wib(terkini['waktu'].iloc[0]) if len(terkini) else '-'}.", icon=None)
elif sumber_pilihan.startswith("Live"):
    st.warning(f"🟠 {pesan} Snapshot sampel: {fmt_wib(terkini['waktu'].iloc[0]) if len(terkini) else '-'}.")
else:
    info = muat_data.info_sampel(jejak)
    st.info(
        f"📼 Sampel offline: {info['snapshot']} snapshot, {info['pesawat']} pesawat unik, "
        f"{fmt_wib(info['mulai'])} sampai {fmt_wib(info['selesai'])}."
    )

ringkas = analisis.ringkasan_kepemilikan(terkini_f)
k1, k2, k3, k4, k5 = st.columns([1, 1.1, 1, 1.5, 1.9])
k1.metric("Pesawat terdeteksi", ringkas["total"])
k2.metric("Registrasi Indonesia", f"{ringkas['persen_indonesia']}%", f"{ringkas['indonesia']} pesawat", delta_color="off")
k3.metric("Registrasi asing", ringkas["asing"], f"{ringkas['jumlah_negara']} negara", delta_color="off")
k4.metric("Negara teratas", ringkas["negara_teratas"])
k5.metric("Maskapai teratas", ringkas["maskapai_teratas"])

if mode_belajar:
    with st.expander("🎓 Apa itu ADS-B dan dari mana angka ini berasal?", expanded=True):
        st.markdown(
            """
            **ADS-B** (Automatic Dependent Surveillance–Broadcast) adalah sinyal radio yang dipancarkan pesawat
            sekitar satu kali per detik, berisi identitas (alamat ICAO 24-bit), posisi GPS, ketinggian, kecepatan,
            dan arah. Sinyal ini tidak terenkripsi, sehingga siapa pun dengan antena murah dapat menerimanya.

            **OpenSky Network** mengumpulkan sinyal dari ribuan penerima sukarelawan dan menyediakannya lewat API.
            Aplikasi ini memanggil `GET /api/states/all` dengan kotak batas Indonesia (`src/opensky.py`), lalu:

            1. memberi nama 17 kolom tanpa nama menjadi DataFrame (`states_ke_dataframe`),
            2. menebak maskapai dari 3 huruf pertama callsign (`src/maskapai.py`),
            3. menebak fase terbang dari ketinggian dan laju vertikal (`src/analisis.py`).

            **"Registrasi Indonesia"** mengikuti kolom `origin_country` OpenSky, yaitu negara tempat pesawat
            terdaftar (ditentukan dari blok alamat ICAO), bukan negara maskapai yang mengoperasikannya.
            """
        )

# Navigasi memakai segmented control, bukan st.tabs: tab tersembunyi berukuran 0 piksel
# membuat Leaflet (terutama HeatMap) gagal menggambar peta kedua. Hanya satu halaman dirender.
HALAMAN = ["🛩️ Peta langsung", "🔥 Heatmap jejak", "👑 Siapa pemilik langit", "📋 Data & sumber", "🧭 Cara kerja"]
halaman = st.segmented_control("Halaman", HALAMAN, default=HALAMAN[0], label_visibility="collapsed")
if halaman is None:
    halaman = HALAMAN[0]

# ------------------------------------------------------------------ tab peta
if halaman == HALAMAN[0]:
    if terkini_f.empty:
        st.warning("Tidak ada pesawat yang lolos filter.")
    else:
        m = peta.peta_pesawat(terkini_f, bandara)
        st_folium(m, use_container_width=True, height=560, returned_objects=[], key="peta_pesawat")
        legenda = " · ".join(
            f"<span style='color:{w};font-weight:700'>■</span> {k}" for k, w in peta.WARNA_KELOMPOK.items()
        )
        st.markdown(f"<div style='font-size:13px'>{legenda} · <span style='color:#fff'>●</span> bandara</div>",
                    unsafe_allow_html=True)
        st.caption("Klik ikon untuk detail: callsign, maskapai, ketinggian, kecepatan, bandara terdekat.")

    if mode_belajar:
        with st.expander("🎓 Bagaimana ikon pesawat diputar sesuai arah?"):
            st.markdown(
                """
                Folium tidak punya marker berbentuk pesawat, jadi `src/peta.py` membuat **DivIcon**: potongan HTML
                berisi SVG pesawat dengan gaya `transform: rotate(<arah>deg)`. Kolom `arah` OpenSky adalah
                *true track* dalam derajat searah jarum jam dari utara, dan SVG-nya digambar menghadap ke atas,
                sehingga keduanya langsung cocok tanpa konversi.

                ```python
                svg = f'<svg ... style="transform: rotate({arah:.0f}deg)"><path d="..." fill="{warna}"/></svg>'
                folium.DivIcon(html=svg, icon_size=(22, 22), icon_anchor=(11, 11))
                ```
                `icon_anchor` di tengah penting agar pesawat berputar pada porosnya, bukan pada sudut kiri atas.
                """
            )

# ------------------------------------------------------------------ tab heatmap
if halaman == HALAMAN[1]:
    info_jejak = muat_data.info_sampel(jejak_f)
    if sumber == "live" and info_jejak["snapshot"] < 3:
        st.info(
            f"Jejak live baru {info_jejak['snapshot']} snapshot. Tekan **Segarkan** beberapa kali (jeda 30 detik) "
            "agar jejak terkumpul, atau beralih ke **Sampel offline** untuk melihat heatmap dari rekaman penuh."
        )
    kh1, kh2, kh3 = st.columns(3)
    ukuran_sel = kh1.select_slider("Ukuran sel kepadatan (derajat)", [0.25, 0.5, 1.0], value=0.5)
    radius_heat = kh2.slider("Radius heatmap", 6, 30, 14)
    jumlah_sel = kh3.slider("Sel terpadat ditandai", 0, 10, 5)
    grid = analisis.grid_kepadatan(jejak_f, ukuran_sel)
    teratas = grid.head(jumlah_sel).copy()
    if not teratas.empty:
        teratas["label"] = [analisis.label_lokasi(a, b, bandara) for a, b in zip(teratas["lat_tengah"], teratas["lon_tengah"])]
    if jejak_f.empty:
        st.warning("Tidak ada jejak yang lolos filter.")
    else:
        m2 = peta.peta_heatmap(jejak_f, bandara, teratas if jumlah_sel else None, radius=radius_heat, blur=radius_heat + 4)
        st_folium(m2, use_container_width=True, height=560, returned_objects=[], key="peta_heatmap")
    st.caption(
        f"Heatmap dibangun dari {info_jejak['baris']:,} posisi, {info_jejak['snapshot']} snapshot, "
        f"{info_jejak['pesawat']} pesawat unik ({fmt_wib(info_jejak['mulai'])} – {fmt_wib(info_jejak['selesai'])})."
    )

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Sel udara terpadat")
        if teratas.empty:
            st.write("-")
        else:
            tampil = teratas.rename(columns={"label": "Lokasi", "pesawat": "Pesawat unik", "titik": "Posisi terekam",
                                             "lat_tengah": "Lat", "lon_tengah": "Lon"})
            st.dataframe(tampil[["Lokasi", "Pesawat unik", "Posisi terekam", "Lat", "Lon"]],
                         use_container_width=True, hide_index=True)
    with c2:
        st.subheader("Jejak terpanjang dalam rekaman")
        pj = analisis.panjang_jejak_km(jejak_f).head(10)
        if pj.empty:
            st.write("Perlu minimal 2 snapshot.")
        else:
            st.dataframe(pj.rename(columns={"callsign": "Callsign", "maskapai": "Maskapai", "segmen": "Segmen", "km": "Jarak (km)"})
                         [["Callsign", "Maskapai", "Segmen", "Jarak (km)"]], use_container_width=True, hide_index=True)

    if mode_belajar:
        with st.expander("🎓 Mengapa heatmap bisa menunjukkan 'rute' padahal datanya hanya titik?"):
            st.markdown(
                """
                Satu snapshot hanya berisi **posisi sesaat**. Namun jika snapshot diambil setiap 20 detik selama
                20 menit, sebuah pesawat berkecepatan 850 km/jam akan meninggalkan 60 titik sepanjang sekitar 280 km.
                Ratusan pesawat yang melakukan hal yang sama akan menggambar koridor penerbangan dengan sendirinya;
                heatmap hanya "menyalakan" tempat yang banyak titiknya.

                **Grid kepadatan** (`grid_kepadatan` di `src/analisis.py`) bekerja lebih sederhana lagi: koordinat
                dibulatkan ke bawah ke kelipatan ukuran sel, lalu dihitung per sel.

                ```python
                g["lat_sel"] = np.floor(g["lat"] / ukuran_deg)
                g["lon_sel"] = np.floor(g["lon"] / ukuran_deg)
                agg = g.groupby(["lat_sel", "lon_sel"]).agg(titik=("icao24", "size"), pesawat=("icao24", "nunique"))
                ```
                Perhatikan dua ukuran berbeda: `titik` menghitung semua posisi (pesawat lambat atau yang berputar
                menunggu mendarat akan menumpuk), sedangkan `pesawat` menghitung pesawat unik (icao24).
                """
            )

# ------------------------------------------------------------------ tab pemilik
if halaman == HALAMAN[2]:
    if terkini_f.empty:
        st.warning("Tidak ada pesawat yang lolos filter.")
    else:
        g1, g2 = st.columns(2)
        per_negara = analisis.hitung_unik(terkini_f, "negara_asal", 12)
        g1.plotly_chart(
            grafik_batang(per_negara, "pesawat", "negara_asal", "Negara registrasi (snapshot terkini)", sorot="Indonesia", hover="persen"),
            use_container_width=True,
        )
        per_maskapai = analisis.hitung_unik(
            terkini_f[~terkini_f["maskapai"].isin([mk.TIDAK_DIKENAL, mk.PENERBANGAN_UMUM])], "maskapai", 12
        )
        indo_maskapai = {nama for nama, negara in mk.MASKAPAI.values() if negara == "Indonesia"}
        fig_m = grafik_batang(per_maskapai, "pesawat", "maskapai", "Maskapai dari callsign (snapshot terkini)", hover="persen")
        fig_m.update_traces(marker_color=[EMAS if m_ in indo_maskapai else ABU for m_ in per_maskapai["maskapai"]])
        g2.plotly_chart(fig_m, use_container_width=True)
        st.caption("Emas = Indonesia. Pesawat tanpa callsign maskapai (penerbangan umum, militer, kosong) tidak masuk grafik maskapai.")

        g3, g4 = st.columns(2)
        per_fase = analisis.hitung_unik(terkini_f, "fase")
        g3.plotly_chart(grafik_batang(per_fase, "pesawat", "fase", "Fase penerbangan", hover="persen"), use_container_width=True)

        alt = terkini_f["alt_kaki"].dropna()
        fig_alt = px.histogram(alt, nbins=18, template=TEMPLATE, title="Sebaran ketinggian (kaki)",
                               color_discrete_sequence=[EMAS])
        fig_alt.update_layout(showlegend=False, xaxis_title="kaki", yaxis_title="pesawat", bargap=0.08,
                              margin=dict(l=10, r=10, t=50, b=10), paper_bgcolor="rgba(0,0,0,0)",
                              plot_bgcolor="rgba(0,0,0,0)", height=360)
        fig_alt.update_traces(hovertemplate="%{x} kaki<br>%{y} pesawat<extra></extra>")
        g4.plotly_chart(fig_alt, use_container_width=True)

        st.subheader("Bandara tersibuk (perkiraan dari pesawat rendah di sekitarnya)")
        sibuk = analisis.bandara_tersibuk(jejak_f, bandara).head(12)
        if sibuk.empty:
            st.write("Tidak ada pesawat rendah di sekitar bandara dalam daftar.")
        else:
            sibuk["label"] = sibuk["kota"] + " (" + sibuk["kode"] + ")"
            st.plotly_chart(
                grafik_batang(sibuk, "pesawat", "label", "Pesawat unik < 3.500 m dalam 60 km, sepanjang rekaman",
                              sorot=None),
                use_container_width=True,
            )
            st.caption("Bandara di luar daftar `data/bandara.csv` tidak dihitung. Changi dan Hang Nadim hanya "
                       "terpaut 30 km, sehingga setiap posisi dihitung untuk bandara terdekatnya saja.")

    if mode_belajar:
        with st.expander("🎓 Mengapa menghitung pesawat unik, bukan baris?"):
            st.markdown(
                """
                Dalam jejak, satu pesawat muncul di banyak snapshot. Jika yang dihitung adalah **baris**, pesawat
                yang terbang lama (atau yang berputar menunggu giliran mendarat) akan terlihat seperti 60 pesawat.
                Karena itu seluruh grafik memakai `groupby(...)["icao24"].nunique()`: alamat transponder 24-bit
                bersifat unik per badan pesawat, sehingga hitungannya benar-benar jumlah pesawat.

                Perbedaan **negara registrasi** dan **negara maskapai** juga penting: pesawat sewaan (leasing)
                bisa terdaftar di Irlandia atau Malta tetapi dioperasikan maskapai Indonesia. Kolom
                `negara_maskapai` pada tabel data mencoba menebak dari callsign; kolom `negara_asal` adalah
                registrasi menurut OpenSky.
                """
            )

# ------------------------------------------------------------------ tab data
if halaman == HALAMAN[3]:
    st.subheader("Snapshot terkini")
    kolom_tampil = ["callsign", "maskapai", "negara_asal", "negara_maskapai", "fase", "alt_kaki", "kecepatan_kmh",
                    "arah", "laju_vertikal", "lat", "lon", "bandara_terdekat", "jarak_bandara_km", "icao24", "squawk", "waktu"]
    st.dataframe(terkini_f[kolom_tampil].sort_values("callsign"), use_container_width=True, hide_index=True, height=420)
    d1, d2 = st.columns(2)
    d1.download_button("⬇️ Unduh snapshot terkini (CSV)", terkini_f.to_csv(index=False).encode("utf-8"),
                       "snapshot_terkini.csv", "text/csv", use_container_width=True)
    d2.download_button("⬇️ Unduh seluruh jejak (CSV)", jejak_f.to_csv(index=False).encode("utf-8"),
                       "jejak.csv", "text/csv", use_container_width=True)

    st.subheader("Bandara acuan")
    st.dataframe(bandara, use_container_width=True, hide_index=True, height=260)

    st.subheader("Sumber & keterbatasan data")
    st.markdown(
        f"""
        - **Posisi pesawat**: [OpenSky Network](https://opensky-network.org) REST API, endpoint `/states/all`,
          kotak batas lintang {opensky.BBOX_INDONESIA['lamin']} s.d. {opensky.BBOX_INDONESIA['lamax']}, bujur
          {opensky.BBOX_INDONESIA['lomin']} s.d. {opensky.BBOX_INDONESIA['lomax']}. Lisensi data OpenSky untuk
          penggunaan non-komersial; lihat [ketentuan OpenSky](https://opensky-network.org/about/terms-of-use).
        - **Bandara**: koordinat dari Wikipedia, dibulatkan 4 desimal (`data/bandara.csv`).
        - **Maskapai**: tebakan dari 3 huruf kode ICAO pada callsign (`src/maskapai.py`). Daftar tidak lengkap.
        - **Cakupan tidak merata.** OpenSky bergantung pada penerima sukarelawan. Jawa, Bali, Sumatera bagian
          timur, dan sekitar Singapura tercakup baik; Indonesia timur dan laut lepas sering kosong. Ruang udara
          yang terlihat "sepi" belum tentu benar-benar sepi.
        - **Pesawat tanpa ADS-B tidak terlihat**: sebagian pesawat militer, pesawat kecil lama, dan penerbangan
          yang sengaja mematikan transponder.
        - **Disclaimer.** Seluruh data berasal dari sumber publik dan bersifat edukatif; bukan data operasional
          penerbangan dan tidak boleh dipakai untuk navigasi atau keputusan keselamatan. Proyek ini merupakan
          portofolio pribadi dan tidak berafiliasi dengan OpenSky Network, maskapai, atau otoritas penerbangan.
        """
    )

# ------------------------------------------------------------------ tab cara kerja
if halaman == HALAMAN[4]:
    st.subheader("Alur data")
    st.graphviz_chart(
        """
        digraph G {
          rankdir=LR; bgcolor="transparent"; node [shape=box, style="rounded,filled", fillcolor="#141d2f",
          fontcolor="#e8ecf4", color="#f2b705", fontname="Helvetica"]; edge [color="#9aa5b1"];
          A [label="Pesawat\\nmemancarkan ADS-B"];
          B [label="Penerima sukarelawan\\nOpenSky Network"];
          C [label="GET /api/states/all\\nsrc/opensky.py"];
          D [label="DataFrame rapi\\nstates_ke_dataframe"];
          E [label="perkaya()\\nmaskapai · fase · bandara terdekat\\nsrc/analisis.py"];
          F [label="Peta Folium\\nsrc/peta.py"];
          G [label="Grafik Plotly\\napp.py"];
          S [label="Sampel offline\\ndata/sample/snapshots.csv", fillcolor="#2a2f3a"];
          A -> B -> C -> D -> E; S -> D; E -> F; E -> G;
        }
        """
    )
    st.markdown(
        """
        | Langkah | File | Inti |
        |---|---|---|
        | Tarik data | `src/opensky.py` | Satu permintaan HTTP dengan kotak batas Indonesia; cache 30 detik; gagal → sampel |
        | Rapikan | `src/opensky.py` | 17 kolom tanpa nama → DataFrame bernama, callsign dibersihkan, waktu UTC |
        | Perkaya | `src/analisis.py` | Tebak maskapai, fase terbang, bandara terdekat (haversine) |
        | Peta | `src/peta.py` | DivIcon SVG berputar sesuai arah; HeatMap dari seluruh jejak |
        | Hitung | `src/analisis.py` | Pesawat unik per negara/maskapai, grid kepadatan, bandara tersibuk, panjang jejak |
        | Rekam sampel | `scripts/kumpulkan_sampel.py` | Menyimpan N snapshot ke CSV agar aplikasi bisa dipakai offline |

        **Kuota OpenSky.** Pengguna anonim mendapat sekitar 400 kredit per hari. Kotak seluas Indonesia
        (lebih dari 400 derajat persegi) berbiaya 4 kredit per permintaan, jadi kira-kira 100 permintaan per hari.
        Dengan cache 30 detik, menonton selama satu jam tanpa henti menghabiskan sekitar separuhnya.
        Jika kuota habis, aplikasi otomatis beralih ke sampel offline dan memberi tahu lewat pesan oranye.
        """
    )
    if mode_belajar:
        with st.expander("🎓 Rumus haversine yang dipakai untuk 'bandara terdekat'"):
            st.markdown(
                r"""
                Jarak lingkaran besar antara dua titik di permukaan bola berjari-jari $R$:

                $$a = \sin^2\!\left(\frac{\Delta\varphi}{2}\right) + \cos\varphi_1 \cos\varphi_2 \sin^2\!\left(\frac{\Delta\lambda}{2}\right),
                \qquad d = 2R \arcsin\sqrt{a}$$

                dengan $\varphi$ lintang dan $\lambda$ bujur dalam radian, $R = 6.371$ km. Untuk 50 pesawat dan 36
                bandara perhitungannya hanya 1.800 kali, jadi versi Python biasa sudah cukup cepat. Versi vektor
                (`haversine_vektor`) dipakai saat satu bandara dibandingkan dengan ribuan posisi jejak sekaligus.
                """
            )
