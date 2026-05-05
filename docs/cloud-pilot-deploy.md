# Pelixi Pilot Cloud Deploy (Render)

Bu not, Pelixi'yi hizlica 3-4 kullanicilik pilot olarak buluta cikarmak icin hazirlandi.

## 1) Gereken ortam degiskenleri

- `PELIXI_DB_BACKEND=sqlite` (kisa pilot icin)
- `MYNOTES_APP_DIR=/var/data/pelixi` (kalici disk klasoru)
- `PORT` (Render otomatik verir, elle set etme)
- `PELIXI_HOST=0.0.0.0` (opsiyonel)

Not: Kisa pilotta SQLite calisir, ama final canli kullanimda PostgreSQL'e gecilmesi onerilir.

## 2) Render servis olusturma

1. Repo'yu GitHub'a push et.
2. Render > New > Web Service.
3. Repo sec.
4. Build Command: `pip install -r requirements.txt`
5. Start Command: `python run.py`
6. Instance Type: en kucuk plan yeterli.

## 3) Kalici disk baglama (SQLite icin kritik)

1. Render servisinde Disks bolumune gir.
2. En az 1 disk ekle.
3. Mount path olarak `/var/data` sec.
4. Env degiskeninde `MYNOTES_APP_DIR=/var/data/pelixi` kullan.

Disk baglamazsan SQLite verisi deploy/restart sonrasi kaybolabilir.

## 4) Domain baglama

1. Render servisinde Custom Domains bolumune `pelixi.com` ve `www.pelixi.com` ekle.
2. Sana verilen DNS kayitlarini domain paneline gir:
   - apex (`pelixi.com`) icin A/ALIAS
   - `www` icin CNAME
3. SSL aktif olunca hem `https://pelixi.com` hem `https://www.pelixi.com` calismali.

## 5) Pilot guvenlik kontrol listesi

- Setup tamamlandiktan sonra yeni admin olusturma yolunu kapat (uygulama zaten ilk userdan sonra setup'i kapatiyor).
- Sadece test kullanicilarini ac.
- Guclu sifre zorunlulugu uygula.
- Loglari haftalik kontrol et.
- En az gunluk manuel backup al.

## 6) Pilot sonrasi gecis

Pilot bittikten sonra:

1. PostgreSQL olustur.
2. `scripts/migrate_sqlite_to_postgres.py` ile veri tasima dry-run yap.
3. `PELIXI_DB_BACKEND=postgres` ve `DATABASE_URL` ile yeni ortama gec.
