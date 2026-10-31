# Sumber dan keterbatasan data

## 1. Posisi pesawat: OpenSky Network

| Hal | Keterangan |
|---|---|
| Sumber | [OpenSky Network](https://opensky-network.org), REST API `GET /api/states/all` |
| Dokumentasi | https://openskynetwork.github.io/opensky-api/rest.html |
| Kotak batas | lintang -11,5° s.d. 6,5°; bujur 94,5° s.d. 141,5° (Sabang–Merauke dengan margin; Singapura dan Semenanjung Malaysia bagian selatan ikut masuk) |
| Akses | anonim, tanpa kunci API; sekitar 400 kredit per hari, kotak ini berbiaya 4 kredit per permintaan |
| Resolusi waktu | 10 detik untuk pengguna anonim |
| Lisensi | data OpenSky untuk penggunaan non-komersial dan riset, lihat [Terms of Use](https://opensky-network.org/about/terms-of-use) |

Kolom yang dipakai dari setiap *state vector* (nama kolom di aplikasi dalam kurung):
`icao24`, `callsign`, `origin_country` (`negara_asal`), `time_position`, `last_contact`, `longitude` (`lon`),
`latitude` (`lat`), `baro_altitude` (`alt_baro_m`), `on_ground` (`di_darat`), `velocity` (`kecepatan_ms`),
`true_track` (`arah`), `vertical_rate` (`laju_vertikal`), `geo_altitude` (`alt_geo_m`), `squawk`, `spi`,
`position_source` (`sumber_posisi`).

**Keterbatasan penting**

- **Cakupan bergantung pada penerima sukarelawan.** Jawa, Bali, pantai timur Sumatera, dan kawasan Singapura
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
tidak berafiliasi dengan OpenSky Network, maskapai mana pun, AirNav Indonesia, maupun otoritas penerbangan.
