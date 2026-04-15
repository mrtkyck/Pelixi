# Product Plan

## Urun Tanimi

My Notes; kurum ici is takibini, toplanti kayitlarini, resmi surecleri ve dis paydas ile olan notlari merkezi bir panelde birlestiren bir uygulamadir.

## Hedef Kullanici

- yonetici
- okul/kurum operasyon sorumlusu
- idari personel

## Temel Problem

Bilgiler farkli defterlerde, mesajlarda veya daginik dosyalarda tutuldugunda takip zorlasir. Bu uygulama tum kritik kayitlari tek ekranda toplayarak unutulan isleri ve kacirilan tarihleri azaltmayi hedefler.

## Moduller

### 1. Dashboard

Amac: bugun ve yakin donemde dikkat edilmesi gerekenleri tek ekranda gostermek.

Bilesenler:

- bugunun gorevleri
- geciken gorevler
- yaklasan evrak tarihleri
- son eklenen toplanti notlari
- sonraki tedarikci gorusmeleri

### 2. Gorevler

Amac: gunluk yapilacak isleri kategori ve oncelige gore yonetmek.

Alanlar:

- baslik
- aciklama
- kategori
- oncelik
- durum
- son tarih
- ilgili kayit tipi
- etiketler

Islevler:

- yeni gorev ekleme
- tamamlandi / bekliyor / ertelendi durumlari
- filtreleme
- son tarihe gore listeleme

### 3. Toplanti Notlari

Amac: ogretmenler, kurucular ve diger paydaslarla yapilan toplanti detaylarini kaydetmek.

Alanlar:

- toplanti basligi
- tarih
- katilimcilar
- toplanti tipi
- gundem
- notlar
- kararlar
- takip maddeleri

Islevler:

- toplanti karti olusturma
- toplanti icinden gorev uretme
- tarih bazli listeleme

### 4. Resmi Evrak Takibi

Amac: teslim tarihi olan resmi surecleri takip etmek.

Alanlar:

- evrak adi
- kurum
- evrak tipi
- aciklama
- son teslim tarihi
- durum
- sorumlu kisi
- dosya yolu veya ek bilgisi

Durumlar:

- hazirlaniyor
- beklemede
- teslim edildi
- gecikti

### 5. Tekrarlayan Evraklar

Amac: belirli periyotlarla yinelenen resmi veya idari isleri unutulmadan takip etmek.

Alanlar:

- kayit adi
- kategori
- tekrar tipi
- son tamamlanma tarihi
- sonraki tarih
- hatirlatma gunu
- sorumlu kisi
- not

Tekrar tipleri:

- aylik
- 3 aylik
- 6 aylik
- yillik
- ozel periyot

### 6. Tedarikciler

Amac: firma kartlarini ve gorusme gecmisini duzenli tutmak.

Alanlar:

- firma adi
- yetkili kisi
- telefon
- e-posta
- hizmet alani
- fiyat bilgisi
- notlar
- son gorusme tarihi
- sonraki gorusme tarihi

Islevler:

- tedarikci karti olusturma
- gorusme notu ekleme
- teklif veya belge takibi

## Menu Yapisi

- Dashboard
- Gorevler
- Toplanti Notlari
- Evrak Takibi
- Tekrarlayan Evraklar
- Tedarikciler
- Ayarlar

## Ilk Surum Kapsami

Ilk surumde gelmesi gerekenler:

- Dashboard ozet kartlari
- gorev ekleme ve listeleme
- toplanti notu kaydetme
- evrak kaydi olusturma ve son tarih takibi
- tedarikci karti ekleme

Ikinci asamaya birakilabilecekler:

- dosya yukleme
- gelismis raporlama
- bildirim sistemi
- kullanici rolleri
- tekrar eden evraklar icin otomatik zamanlama motoru

## Arayuz Onerisi

Tasarim dili:

- sade
- kurumsal
- hizli kullanima uygun

Ekran karakteri:

- solda sabit menu
- ustte hizli arama
- her modulde filtre alanlari
- kart ve tablo karisik kullanim

Renk mantigi:

- kirmizi: geciken
- sari: yaklasan
- yesil: tamamlandi
- mavi: bilgi ve not

## Kullanici Akislari

### Gunluk Kullanim

1. Kullanici Dashboard ekranini acar.
2. Bugun yapilacak gorevleri gorur.
3. Yaklasan evrak veya toplanti takibini kontrol eder.
4. Gerekiyorsa yeni gorev veya not ekler.

### Toplanti Sonrasi Akis

1. Toplanti notu kaydi acilir.
2. Gorusulen konular ve kararlar yazilir.
3. Toplanti icindeki maddelerden gorevler olusturulur.
4. Takip tarihi gereken maddeler ajandaya dusurulur.

### Evrak Takip Akisi

1. Yeni evrak kaydi eklenir.
2. Son tarih ve sorumlu kisi belirlenir.
3. Durum degistikce kayit guncellenir.
4. Geciken veya yaklasan kayitlar Dashboard'a yansir.
