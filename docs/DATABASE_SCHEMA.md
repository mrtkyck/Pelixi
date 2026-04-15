# Database Schema

## Genel Yaklasim

Baslangic icin SQLite yeterlidir. Veri modeli sade tutulur; notlar, gorevler ve takip kalemleri birbirine baglanabilir olacak sekilde tasarlanir.

## Tablolar

### 1. tasks

Gunluk yapilacak islerin tutuldugu ana tablo.

Alanlar:

- `id` INTEGER PRIMARY KEY
- `title` TEXT NOT NULL
- `description` TEXT
- `category` TEXT NOT NULL
- `priority` TEXT NOT NULL
- `status` TEXT NOT NULL
- `due_date` DATETIME
- `related_type` TEXT
- `related_id` INTEGER
- `created_at` DATETIME NOT NULL
- `updated_at` DATETIME NOT NULL

Not:

`related_type` alani bir gorevin bir toplantiya, evraka veya tedarikci kaydina bagli olup olmadigini belirtir.

### 2. meeting_notes

Toplanti iceriklerinin tutuldugu tablo.

Alanlar:

- `id` INTEGER PRIMARY KEY
- `title` TEXT NOT NULL
- `meeting_type` TEXT
- `meeting_date` DATETIME NOT NULL
- `participants` TEXT
- `agenda` TEXT
- `notes` TEXT
- `decisions` TEXT
- `follow_up_items` TEXT
- `created_at` DATETIME NOT NULL
- `updated_at` DATETIME NOT NULL

Not:

`participants` ve `follow_up_items` ilk surumde JSON veya metin olarak saklanabilir.

### 3. documents

Resmi evrak ve tarihli takip kayitlari icin tablo.

Alanlar:

- `id` INTEGER PRIMARY KEY
- `title` TEXT NOT NULL
- `institution` TEXT
- `document_type` TEXT
- `description` TEXT
- `status` TEXT NOT NULL
- `due_date` DATETIME
- `submitted_at` DATETIME
- `responsible_person` TEXT
- `file_path` TEXT
- `created_at` DATETIME NOT NULL
- `updated_at` DATETIME NOT NULL

### 4. recurring_documents

Periyodik evrak veya rutin idari isler icin tablo.

Alanlar:

- `id` INTEGER PRIMARY KEY
- `title` TEXT NOT NULL
- `category` TEXT
- `frequency` TEXT NOT NULL
- `custom_interval_days` INTEGER
- `last_completed_at` DATETIME
- `next_due_date` DATETIME NOT NULL
- `reminder_days_before` INTEGER DEFAULT 7
- `responsible_person` TEXT
- `notes` TEXT
- `is_active` INTEGER NOT NULL DEFAULT 1
- `created_at` DATETIME NOT NULL
- `updated_at` DATETIME NOT NULL

### 5. suppliers

Tedarikci firma kartlari icin tablo.

Alanlar:

- `id` INTEGER PRIMARY KEY
- `company_name` TEXT NOT NULL
- `contact_name` TEXT
- `phone` TEXT
- `email` TEXT
- `service_type` TEXT
- `price_notes` TEXT
- `notes` TEXT
- `last_contact_at` DATETIME
- `next_contact_at` DATETIME
- `created_at` DATETIME NOT NULL
- `updated_at` DATETIME NOT NULL

### 6. supplier_interactions

Tedarikci ile yapilan gorusme ve not gecmisi icin tablo.

Alanlar:

- `id` INTEGER PRIMARY KEY
- `supplier_id` INTEGER NOT NULL
- `interaction_date` DATETIME NOT NULL
- `subject` TEXT
- `notes` TEXT
- `next_action_date` DATETIME
- `created_at` DATETIME NOT NULL

Iliski:

- `supplier_id` -> `suppliers.id`

## Onerilen Enum Degerleri

### Task status

- `pending`
- `in_progress`
- `completed`
- `cancelled`

### Task priority

- `low`
- `medium`
- `high`
- `critical`

### Document status

- `preparing`
- `waiting`
- `submitted`
- `overdue`

### Frequency

- `monthly`
- `quarterly`
- `semiannual`
- `yearly`
- `custom`

## Iliskiler

- Bir `meeting_note` kaydindan birden fazla `task` uretilebilir.
- Bir `document` kaydina bagli gorev acilabilir.
- Bir `supplier` kaydinin birden fazla `supplier_interaction` kaydi olabilir.
- Bir `task`, `related_type` ve `related_id` ile baska modullere baglanabilir.

## Ilk Surum Icin Notlar

- Baslangicta kullanici yonetimi olmadan tek kullanicili yapi yeterli olabilir.
- Dosya yukleme ilk asamada sadece `file_path` olarak tutulabilir.
- JSON alan ihtiyaci dogarsa SQLite ile basit metin saklama kullanilabilir.
