# 🏋️ Latihan

Diurutkan dari yang mudah ke yang lebih menantang. Setiap latihan dilengkapi petunjuk dan kunci jawaban yang dapat
dibuka. Usahakan mencoba minimal 10 menit sebelum membuka kunci. Setelah setiap latihan, jalankan
`python -m pytest tests/ -v` dan `streamlit run app.py`.

Tingkat: ⭐ cukup edit data/teks · ⭐⭐ ubah kode yang ada · ⭐⭐⭐ tulis fungsi dan tes baru

---

### Latihan 1 — Menambah bandara (cukup edit CSV) ⭐

Tambahkan **Bandara Komodo, Labuan Bajo**
(kode `LBJ`, kota `Labuan Bajo`, lat `-8.4866`, lon `119.8891`) ke `data/bandara.csv`.
Buka tab Data & sumber dan pastikan ia muncul di tabel bandara, lalu cek tab Peta: ada titik putih baru di Flores barat.

<details><summary>Petunjuk</summary>
Satu baris baru di akhir file dengan urutan kolom <code>kode,nama,kota,negara,lat,lon</code>. Tidak ada koma di dalam nilai, jadi tidak perlu tanda kutip.
</details>

<details><summary>Kunci</summary>

```
LBJ,Komodo,Labuan Bajo,Indonesia,-8.4866,119.8891
```
Tes `test_bandara_csv_valid` memeriksa koordinat masih di dalam kotak dan kode tetap unik.
</details>

---

### Latihan 2 — Menambah maskapai ke kamus ⭐

Pesawat kargo **Cardig Air** memakai kode ICAO `CAD`. Tambahkan ke `MASKAPAI` di `src/maskapai.py` agar callsign
seperti `CAD123` tidak lagi "Tidak dikenal".

<details><summary>Petunjuk</summary>
Format tiap entri: <code>"KODE": ("Nama", "Negara")</code>. Letakkan di blok Indonesia.
</details>

<details><summary>Kunci</summary>

```python
"CAD": ("Cardig Air", "Indonesia"),
```
Periksa: `python -c "from src import maskapai; print(maskapai.tebak_maskapai('CAD123'))"`.
</details>

---

### Latihan 3 — Mengubah ambang fase terbang ⭐

Ambang naik/turun saat ini 2,5 m/s. Ubah menjadi 1,5 m/s dan lihat berapa banyak pesawat yang berpindah dari
"Jelajah" ke "Naik"/"Turun" di tab Siapa pemilik langit (mode sampel). Lalu kembalikan ke 2,5.

<details><summary>Petunjuk</summary>
Cari angka <code>2.5</code> di fungsi <code>fase_terbang</code> (ada tiga tempat). Tes <code>test_fase_terbang</code> tetap lulus untuk kedua ambang karena data ujinya jauh dari ambang; pikirkan kasus uji yang akan membedakannya.
</details>

<details><summary>Kunci</summary>
Ganti tiga <code>2.5</code> menjadi <code>1.5</code>. Kasus uji pembeda: <code>fase_terbang(9000, 2.0, False)</code> menghasilkan "Jelajah" pada ambang 2,5 tetapi "Naik" pada ambang 1,5. Lebih rapi lagi: jadikan ambang sebuah konstanta <code>AMBANG_VERTIKAL = 2.5</code> di atas fungsi.
</details>

---

### Latihan 4 — KPI baru: kecepatan rata-rata ⭐⭐

Tambahkan kartu metrik keenam di `app.py`: **kecepatan rata-rata (km/jam)** pesawat yang sedang di udara dalam
snapshot terkini.

<details><summary>Petunjuk</summary>
Ganti <code>st.columns(5)</code> menjadi 6. Saring <code>terkini_f[terkini_f["fase"] != "Di darat"]</code>, lalu <code>["kecepatan_kmh"].mean()</code>. Hati-hati jika hasilnya kosong (NaN): tampilkan "-".
</details>

<details><summary>Kunci</summary>

```python
udara = terkini_f[terkini_f["fase"] != "Di darat"]
rata = udara["kecepatan_kmh"].mean()
k6.metric("Kecepatan rata-rata", f"{rata:,.0f} km/jam" if pd.notna(rata) else "-")
```
</details>

---

### Latihan 5 — Filter "hanya di atas Indonesia" ⭐⭐

Kotak batas mencakup Singapura dan Malaysia selatan. Tambahkan checkbox di sidebar yang menyembunyikan pesawat
dengan `bandara_terdekat` milik bandara di luar Indonesia.

<details><summary>Petunjuk</summary>
Anda punya <code>bandara</code> (DataFrame) dengan kolom <code>negara</code>. Buat himpunan kode bandara Indonesia, lalu tambahkan satu <code>if</code> di <code>terapkan_filter</code>.
</details>

<details><summary>Kunci</summary>

```python
hanya_indonesia = st.checkbox("Hanya sekitar bandara Indonesia", value=False)
...
kode_indonesia = set(bandara.loc[bandara["negara"] == "Indonesia", "kode"])
if hanya_indonesia:
    hasil = hasil[hasil["bandara_terdekat"].isin(kode_indonesia)]
```
Ini pendekatan kasar: pesawat di atas Laut Natuna bisa "terdekat" ke Kuching. Pendekatan yang benar memerlukan poligon batas negara (lihat latihan 10).
</details>

---

### Latihan 6 — Grafik arah terbang (rose chart) ⭐⭐

Di tab Siapa pemilik langit, tambahkan grafik polar Plotly yang menunjukkan berapa pesawat terbang ke tiap arah
mata angin (8 sektor: U, TL, T, TG, S, BD, B, BL).

<details><summary>Petunjuk</summary>
Sektor = <code>round(arah / 45) % 8</code>. Hitung pesawat unik per sektor dengan <code>hitung_unik</code>, lalu <code>go.Barpolar(r=..., theta=[0, 45, 90, ...])</code>.
</details>

<details><summary>Kunci</summary>

```python
label = ["U", "TL", "T", "TG", "S", "BD", "B", "BL"]
d = terkini_f.dropna(subset=["arah"]).copy()
d["sektor"] = (d["arah"].round(-1) / 45).round().astype(int) % 8
per = d.groupby("sektor")["icao24"].nunique().reindex(range(8), fill_value=0)
fig = go.Figure(go.Barpolar(r=per.values, theta=[i * 45 for i in range(8)], marker_color=EMAS))
fig.update_layout(template=TEMPLATE, polar=dict(angularaxis=dict(direction="clockwise", rotation=90,
                  tickvals=[i * 45 for i in range(8)], ticktext=label)), title="Arah terbang")
st.plotly_chart(fig, use_container_width=True)
```
</details>

---

### Latihan 7 — Fungsi baru + tes: pesawat tercepat ⭐⭐⭐

Tulis `analisis.pesawat_tercepat(df, n=5)` yang mengembalikan DataFrame `[callsign, maskapai, kecepatan_kmh, alt_kaki]`
untuk n pesawat tercepat (unik per icao24, ambil kecepatan maksimumnya). Tulis dua tes: urutan menurun, dan
DataFrame kosong tidak error.

<details><summary>Petunjuk</summary>
<code>df.sort_values("kecepatan_kmh", ascending=False).drop_duplicates("icao24").head(n)</code>. Untuk tes, pakai fixture <code>df</code> yang sudah ada di <code>tests/test_analisis.py</code>.
</details>

<details><summary>Kunci</summary>

```python
def pesawat_tercepat(df: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    kolom = ["callsign", "maskapai", "kecepatan_kmh", "alt_kaki"]
    if df.empty:
        return pd.DataFrame(columns=kolom)
    return (df.sort_values("kecepatan_kmh", ascending=False)
              .drop_duplicates("icao24").head(n)[kolom].reset_index(drop=True))

def test_pesawat_tercepat_urut_menurun(df):
    h = analisis.pesawat_tercepat(df, 3)
    assert list(h["kecepatan_kmh"]) == sorted(h["kecepatan_kmh"], reverse=True)
    assert h.iloc[0]["callsign"] == "UAE5CL"

def test_pesawat_tercepat_kosong():
    assert analisis.pesawat_tercepat(pd.DataFrame(columns=["icao24"])).empty
```
</details>

---

### Latihan 8 — Menyimpan jejak live ke CSV ⭐⭐⭐

Tambahkan tombol di sidebar yang menyimpan `st.session_state["jejak_live"]` ke `data/sample/jejak_sesi.csv`,
sehingga sesi menonton Anda bisa dipakai sebagai sampel baru. Pastikan file itu masuk `.gitignore` jika tidak ingin
dikomit.

<details><summary>Petunjuk</summary>
<code>jejak.drop(columns=["waktu"] + kolom turunan).to_csv(path, index=False)</code>. Kolom turunan (maskapai, fase, dll.) sebaiknya dibuang agar formatnya sama dengan keluaran <code>kumpulkan_sampel.py</code>; <code>perkaya()</code> akan menghitungnya lagi saat dimuat.
</details>

<details><summary>Kunci</summary>

```python
KOLOM_TURUNAN = ["waktu", "maskapai", "negara_maskapai", "fase", "alt_kaki", "kecepatan_kmh",
                 "bandara_terdekat", "jarak_bandara_km"]
if st.button("💾 Simpan jejak sesi"):
    jejak_sesi = st.session_state.get("jejak_live")
    if jejak_sesi is not None and not jejak_sesi.empty:
        tujuan = muat_data.DIR_DATA / "sample" / "jejak_sesi.csv"
        jejak_sesi.drop(columns=KOLOM_TURUNAN, errors="ignore").to_csv(tujuan, index=False)
        st.success(f"Tersimpan: {tujuan.name}")
```
</details>

---

### Latihan 9 — Auto-refresh ⭐⭐⭐

Buat aplikasi menyegarkan diri setiap 30 detik saat mode live, tanpa menekan tombol, tetapi hanya jika pengguna
mengaktifkan toggle "Putar otomatis". Pikirkan dampaknya terhadap batas laju adsb.lol (HTTP 429 bila terlalu rapat).

<details><summary>Petunjuk</summary>
Streamlit punya <code>st.fragment(run_every="30s")</code> untuk menjalankan ulang sebagian halaman secara berkala. Bungkus bagian KPI + peta ke dalam fungsi berdekorator fragment. Alternatif sederhana: <code>time.sleep(30); st.rerun()</code> di akhir skrip, tetapi ini memblokir seluruh halaman.
</details>

<details><summary>Kunci</summary>

```python
putar = st.sidebar.toggle("▶️ Putar otomatis (30 dtk)", value=False)

@st.fragment(run_every="30s" if putar and sumber_pilihan.startswith("Live") else None)
def blok_live():
    live_df.clear()
    terkini, sumber, pesan = live_df()
    ...  # KPI dan peta
blok_live()
```
Dengan 30 detik per siklus dan dua lingkaran per siklus, satu jam menonton = 240 permintaan. adsb.lol tidak punya kuota harian, tetapi menolak permintaan yang terlalu rapat; pertimbangkan jeda 60 detik dan pastikan jeda antarlingkaran tetap ada.
</details>

---

### Latihan 10 — Benar-benar "di atas Indonesia" dengan poligon ⭐⭐⭐

Latihan 5 memakai bandara terdekat sebagai pendekatan. Ganti dengan uji titik-dalam-poligon memakai batas
negara Indonesia dari Natural Earth (GeoJSON) dan pustaka `shapely`.

<details><summary>Petunjuk</summary>
Unduh <code>ne_110m_admin_0_countries.geojson</code> (Natural Earth, domain publik), ambil fitur dengan <code>ADMIN == "Indonesia"</code>, bangun <code>shapely.geometry.shape(...)</code>, lalu <code>poligon.contains(Point(lon, lat))</code> untuk tiap baris. Tambahkan <code>shapely</code> ke <code>requirements.txt</code>.
</details>

<details><summary>Kunci</summary>

```python
import json
from shapely.geometry import shape, Point

def muat_poligon_indonesia(path):
    gj = json.load(open(path, encoding="utf-8"))
    fitur = next(f for f in gj["features"] if f["properties"]["ADMIN"] == "Indonesia")
    return shape(fitur["geometry"])

def tandai_di_atas_indonesia(df, poligon):
    df = df.copy()
    df["di_atas_indonesia"] = [poligon.contains(Point(lon, lat)) for lat, lon in zip(df["lat"], df["lon"])]
    return df
```
Resolusi 110m cukup kasar (pulau kecil hilang). Untuk hasil lebih baik pakai 50m atau 10m, dengan konsekuensi uji <code>contains</code> lebih lambat; <code>shapely.prepared.prep(poligon)</code> mempercepatnya.
</details>
