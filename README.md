# My Notes

My Notes; yapilacak isleri, toplanti notlarini, resmi evrak takibini ve tedarikci gorusmelerini tek yerde toplamak icin planlanan bir yonetim uygulamasidir.

## Proje Amaci

Bu uygulama klasik bir to do list olmaktan ziyade, gunluk operasyonlari takip eden merkezi bir calisma paneli olarak dusunulmustur.

Hedeflenen kullanim alanlari:

- gunluk ve haftalik gorev takibi
- ogretmenler ve kurucular ile yapilan toplantilarin notlari
- resmi evraklarin son tarih ve durum takibi
- aylik veya yillik tekrar eden evrak hatirlatmalari
- tedarikci kartlari ve gorusme gecmisi

## Ilk Surum Modulleri

- Dashboard
- Gorevler
- Toplanti Notlari
- Resmi Evrak Takibi
- Tedarikciler

Tekrarlayan evraklar modulu ilk surumden hemen sonra eklenebilir.

## Klasor Yapisi

- `README.md`: genel proje ozeti
- `docs/PRODUCT_PLAN.md`: ekranlar, akislar ve urun yapisi
- `docs/DATABASE_SCHEMA.md`: veri modeli ve tablo tasarimi

## Mevcut Ilk Surum

Bu klasorde su anda Python standart kutuphanesi ile calisan hafif bir web uygulamasi kurulmustur.

Ozellikler:

- SQLite veritabani
- tarayicidan acilan yonetim paneli
- gorev, toplanti, evrak, tekrarlayan evrak ve tedarikci modulleri
- ilk acilista ornek kayitlar

## Calistirma

Terminalde bu klasorde su komutu calistirin:

```bash
python run.py
```

Ardindan tarayicida su adresi acin:

```text
http://127.0.0.1:8000
```

Pelixi veri klasoru ve sabit yerel port ile calisma ornegi:

```powershell
$env:MYNOTES_APP_DIR="$env:LOCALAPPDATA\Pelixi"
$env:MYNOTES_PORT="8011"
python run.py
```

## PostgreSQL Gecis Hazirligi

Cloud gecisi icin SQLite -> PostgreSQL migration omurgasi hazirlanmistir.

Detayli notlar:
- `docs/postgresql-migration.md`

## Onerilen Sonraki Teknik Adim

Bu ilk surum hizli baslangic icin sade tutuldu. Ileride su yone buyutulebilir:

- frontend: React
- backend: FastAPI
- veritabani: SQLite ile devam veya PostgreSQL'e gecis
