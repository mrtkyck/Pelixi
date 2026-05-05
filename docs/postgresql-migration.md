# Pelixi PostgreSQL Hazirlik Notlari

Bu not, yerel SQLite verisini PostgreSQL'e tasimadan once gereken minimum ortam
degiskenlerini ve komutlari tek yerde toplar.

## 1. Gerekli ortam degiskenleri

Yerel uygulama halen SQLite ile acilir. Migration veya cloud testi icin asagidaki
degiskenler kullanilir:

```powershell
$env:PELIXI_DB_BACKEND="sqlite"
$env:DATABASE_URL="postgresql://USER:PASSWORD@HOST:PORT/DBNAME"
```

Not:
- Uygulamanin mevcut calisan yerel modunu bozmayalim diye backend varsayilani halen
  `sqlite` olarak kalir.
- `DATABASE_URL` yalnizca migration scripti ve sonraki PostgreSQL testleri icin
  gerekecek.

## 2. Migration dry-run

Gercek Pelixi verisini okumak icin:

```powershell
cd "C:\Users\Murat\Desktop\Python Projelerim\Notes"
python scripts\migrate_sqlite_to_postgres.py --sqlite-path "$env:LOCALAPPDATA\Pelixi\data\my_notes.db"
```

Schema onizlemesi icin:

```powershell
python scripts\migrate_sqlite_to_postgres.py --sqlite-path "$env:LOCALAPPDATA\Pelixi\data\my_notes.db" --print-schema
```

## 3. Gercek execute modu

Bu mod yalnizca hedef PostgreSQL bos oldugunda calistirilmalidir:

```powershell
$env:DATABASE_URL="postgresql://USER:PASSWORD@HOST:PORT/DBNAME"
python scripts\migrate_sqlite_to_postgres.py --sqlite-path "$env:LOCALAPPDATA\Pelixi\data\my_notes.db" --execute
```

## 4. Beklenen guvenlikler

Script su korumalara sahiptir:
- kaynak SQLite dosyasi yoksa durur
- `DATABASE_URL` bos ise durur
- hedef PostgreSQL tablolarinda veri varsa durur
- tablo tablo kaynak/hedef kayit sayisini dogrular

## 5. Sonraki adim

Bir sonraki teknik adim:
- PostgreSQL uzerinde ilk test migration
- ardindan Railway web service + PostgreSQL kurulumuna gecis
