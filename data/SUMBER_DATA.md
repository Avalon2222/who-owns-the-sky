# Sumber dan keterbatasan data

## 1. Posisi pesawat live: adsb.lol

| Hal | Keterangan |
|---|---|
| Sumber | [adsb.lol](https://adsb.lol), REST API `GET /v2/lat/{lat}/lon/{lon}/dist/{dist}` |
| Dokumentasi | https://api.adsb.lol/docs |
| Cakupan | dua lingkaran beradius 1.000 mil laut berpusat di (-2,5°, 103°) dan (-2,5°, 131°); hasil dipotong ke kotak batas di bawah |
| Akses | tanpa akun dan tanpa kunci; server menolak permintaan yang terlalu rapat (HTTP 429), sehingga ada jeda 1 detik antarpanggilan dan cache 30 detik |
| Format | satu pesawat = satu objek JSON bergaya readsb (`hex`, `flight`, `r`, `t`, `alt_baro`, `gs`, `track`, `baro_rate`, `lat`, `lon`, ...) |
| Lisensi | [ODbL](https://opendatacommons.org/licenses/odbl/) |

Konversi di `src/adsb.py`: `alt_baro`/`alt_geom` kaki → meter, `gs` knot → m/s, `baro_rate` kaki/menit → m/s,
`alt_baro == "ground"` → `di_darat`. adsb.lol tidak memberi negara registrasi, sehingga `negara_asal` ditebak dari
awalan registrasi (`PK-` Indonesia, `9V-` Singapura, `9M-` Malaysia, ...) dan, bila registrasi kosong, dari blok
alamat ICAO 24-bit; yang tidak dikenali diberi label "Tidak diketahui".

## 1b. Cadangan: OpenSky Network

Dipakai hanya bila adsb.lol gagal, dan untuk merekam sampel offline.

| Hal | Keterangan |
|---|---|
| Sumber | [OpenSky Network](https://opensky-network.org), REST API `GET /api/states/all` |
| Dokumentasi | https://openskynetwork.github.io/opensky-api/rest.html |
| Kotak batas | lintang -11,5° s.d. 6,5°; bujur 94,5° s.d. 141,5° (Sabang–Merauke dengan margin; Singapura dan Semenanjung Malaysia bagian selatan ikut masuk) |
| Akses | anonim, tanpa kunci API; sekitar 400 kredit per hari, kotak ini berbiaya 4 kredit per permintaan. Dengan akun gratis (variabel `OPENSKY_CLIENT_ID`/`OPENSKY_CLIENT_SECRET`) kuota lebih besar. Dari Streamlit Community Cloud server ini tidak dapat dihubungi |
| Resolusi waktu | 10 detik untuk pengguna anonim |
| Lisensi | data OpenSky untuk penggunaan non-komersial dan riset, lihat [Terms of Use](https://opensky-network.org/about/terms-of-use) |

Kolom yang dipakai dari setiap *state vector* (nama kolom di aplikasi dalam kurung):
`icao24`, `callsign`, `origin_country` (`negara_asal`), `time_position`, `last_contact`, `longitude` (`lon`),
`latitude` (`lat`), `baro_altitude` (`alt_baro_m`), `on_ground` (`di_darat`), `velocity` (`kecepatan_ms`),
`true_track` (`arah`), `vertical_rate` (`laju_vertikal`), `geo_altitude` (`alt_geo_m`), `squawk`, `spi`,
`position_source` (`sumber_posisi`).

**Keterbatasan penting**

- **Cakupan bergantung pada penerima sukarelawan** (berlaku untuk adsb.lol maupun OpenSky). Jawa, Bali, pantai timur Sumatera, dan kawasan Singapura
  tercakup baik. Kalimantan tengah, Sulawesi, Maluku, Papua, dan laut lepas sering kosong. Ruang udara yang
  tampak sepi belum tentu sepi.
- **Hanya pesawat yang memancarkan ADS-B/Mode S yang terlihat.** Sebagian pesawat militer dan pesawat kecil tua
  tidak terlihat. Posisi MLAT (`sumber_posisi` = 2) kurang akurat dibanding ADS-B.
- **`origin_country` adalah negara registrasi**, ditentukan dari blok alamat ICAO 24-bit, bukan negara maskapai.
  Pesawat sewaan bisa terdaftar di negara lain.
- Ketinggian barometrik mengacu pada tekanan standar 1013,25 hPa, bukan tinggi sebenarnya di atas tanah.

## 2. Sampel offline: `data/sample/snapshots.csv`

Rekaman beberapa snapshot OpenSky berturut-turut dengan jeda sekitar 20 detik, dibuat memakai
`scripts/kumpulkan_sampel.py`. Satu baris = satu pesawat pada satu snapshot; kolom `waktu_snapshot` (unix time, UTC)
menandai snapshot asalnya. Waktu perekaman tercantum di README. Sampel direkam pada dini hari WIB, sehingga lalu
lintas domestik Indonesia jauh lebih sedikit daripada siang hari dan Singapura mendominasi. Untuk sampel yang
berbeda, jalankan ulang skrip pada jam sibuk.

## 3. Bandara: `data/bandara.csv`

36 bandara utama di dalam kotak batas (30 di Indonesia; Singapura, Malaysia, Brunei, Timor-Leste sebagai tetangga).
Koordinat dari halaman Wikipedia masing-masing bandara, dibulatkan 4 desimal (sekitar 10 m). Daftar ini hanya
dipakai untuk label "bandara terdekat" dan perkiraan bandara tersibuk; bandara di luar daftar tidak dihitung.

## 4. Maskapai: `src/maskapai.py`

Pemetaan 3 huruf kode ICAO pada callsign ke nama maskapai, misalnya `GIA` → Garuda Indonesia. Daftar disusun dari
pengetahuan umum penerbangan dan Wikipedia (daftar kode maskapai ICAO) dan tidak lengkap. Callsign yang berpola
registrasi (`PK-ABC`, `9V-SHA`) dikelompokkan sebagai penerbangan umum, sisanya "Tidak dikenal".

## Disclaimer

Seluruh data berasal dari sumber publik dan disajikan untuk tujuan edukasi dan portofolio. Data ini **bukan** data
operasional penerbangan dan tidak boleh dipakai untuk navigasi, pengawasan, atau keputusan keselamatan. Proyek ini
tidak berafiliasi dengan adsb.lol, OpenSky Network, maskapai mana pun, AirNav Indonesia, maupun otoritas penerbangan.
