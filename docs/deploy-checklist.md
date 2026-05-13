# Pelixi Deploy Checklist (Render)

Bu listeyi her deploydan sonra 2-3 dakikada gecmek icin kullan.

## 1) Git ve Render

- GitHub `main` guncel mi?
- Render servisinde `Manual Deploy -> Deploy latest commit` calistirildi mi?
- Deploy log'da hata yok mu?

## 2) Servis Saglik Kontrolu

- Uygulama aciliyor mu?
- `/events` sayfasi aciliyor mu?
- Login/cikis akisi normal mi?

## 3) Etkinlik Modulu Smoke Test

- `Yeni Etkinlik` modal aciliyor mu?
- `Kademe` acilir liste:
  - coklu secim yapiliyor mu?
  - baska alana tiklayinca liste kapaniyor mu?
- Etkinlik ekleme/guncelleme/silme calisiyor mu?
- Etkinlik detay popup'i aciliyor mu?

## 4) Takvim Kontrolleri

- Sayfa ilk acilista bugunun ayi geliyor mu?
- Resmi tatiller takvimde gorunuyor mu?
- Dini bayramlar otomatik gorunuyor mu?
- Tatil gun numarasi ve tatil satiri kirmizi gorunuyor mu?
- Bir gune tiklayinca o gunun tum etkinlikleri kart olarak aciliyor mu?

## 5) Hata Durumunda Hizli Kontrol

- Render log'da `Start Command` hatasi var mi?
- `python run.py` start komutu dogru mu?
- `requirements.txt` icinde gereken kutuphaneler var mi? (`holidays`, vb.)

## 6) Kisa Not

Cloud ortami icin `PORT` degeri Render tarafindan verilir.
Yerelde varsayilan calisma adresi: `127.0.0.1:8000`.
