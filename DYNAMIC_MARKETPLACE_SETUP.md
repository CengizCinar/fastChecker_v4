# Dynamic Marketplace Support for FastChecker

Bu güncelleme ile FastChecker artık kullanıcının bulunduğu Amazon ülkesine göre dinamik olarak çalışır.

## Desteklenen Marketplaces

### Kuzey Amerika (NA) Bölgesi
- **Amerika Birleşik Devletleri**: `US`
- **Kanada**: `CA` 
- **Meksika**: `MX`

### Avrupa (EU) Bölgesi
- **Almanya**: `DE`
- **İngiltere**: `GB`
- **Fransa**: `FR`
- **İtalya**: `IT`
- **İspanya**: `ES`
- **Hollanda**: `NL`
- **İsveç**: `SE`
- **Polonya**: `PL`
- **Belçika**: `BE`

## Environment Variables Setup

### AWS Credentials (Her iki bölge için ortak)
```bash
AWS_ACCESS_KEY_ID="your_aws_access_key"
AWS_SECRET_ACCESS_KEY="your_aws_secret_key"
```

### NA Bölgesi için (Zorunlu)
```bash
AMAZON_REFRESH_TOKEN="your_na_refresh_token"
AMAZON_LWA_APP_ID="your_na_lwa_app_id"
AMAZON_LWA_CLIENT_SECRET="your_na_lwa_client_secret"
AMAZON_SELLER_ID="your_na_seller_id"
```

### EU Bölgesi için (Opsiyonel)
```bash
EU_REFRESH_TOKEN="your_eu_refresh_token"
EU_LWA_APP_ID="your_eu_lwa_app_id"
EU_LWA_CLIENT_SECRET="your_eu_lwa_client_secret"
EU_SELLER_ID="your_eu_seller_id"
```

## Nasıl Çalışır

### 1. Otomatik Marketplace Tespiti
- Extension, kullanıcının bulunduğu Amazon domain'ini otomatik olarak tespit eder
- `content.js` içindeki `detectMarketplace()` fonksiyonu domain'i marketplace koduna çevirir
- Örnek: `www.amazon.de` → `DE`, `www.amazon.co.uk` → `GB`

### 2. Dinamik Credential Yönetimi
- **AWS Access Keys**: Her iki bölge için aynı AWS credentials kullanılır
- **SP-API Credentials**: NA ve EU bölgeleri için farklı refresh token, app ID ve client secret
- `app.py` içindeki `get_credentials_for_marketplace()` fonksiyonu uygun credentials'ları seçer

### 3. API Çağrıları
- Backend API'ye marketplace parametresi gönderilir
- Backend, marketplace'e göre doğru credentials'ları kullanır
- SP-API çağrıları doğru endpoint ve marketplace ID'leri ile yapılır

## Değişiklikler

### app.py
- `MARKETPLACE_REGIONS` konfigürasyonu eklendi
- AWS credentials her iki bölge için ortak kullanılıyor
- NA ve EU SP-API credentials ayrı ayrı yükleniyor
- `get_credentials_for_marketplace()` fonksiyonu eklendi
- Marketplace validation eklendi

### content.js
- `detectMarketplace()` fonksiyonu eklendi
- API çağrılarına marketplace parametresi eklendi
- Domain-to-marketplace mapping eklendi

### sp-api-helper.js
- Tüm marketplace'ler için doğru endpoint ve marketplace ID'leri eklendi
- GB marketplace'i eklendi (UK alias'ı ile)

### background.js
- Marketplace parametresi zaten destekleniyordu, değişiklik gerekmedi

## Test Etme

1. **Marketplace Detection Test**: `test_marketplace_detection.js` dosyasını browser console'da çalıştırın
2. **Farklı Amazon Domain'lerinde Test**: 
   - amazon.com → US marketplace
   - amazon.de → DE marketplace
   - amazon.co.uk → GB marketplace
   - vb.

## Hata Ayıklama

### Loglar
- Backend loglarında marketplace tespiti görülebilir
- Credential yükleme durumu loglanır
- API çağrıları marketplace bilgisi ile loglanır

### Yaygın Hatalar
1. **"EU credentials not configured"**: EU marketplace'ler için SP-API credentials eksik
2. **"Unsupported marketplace"**: Desteklenmeyen marketplace kodu
3. **"NA credentials not configured"**: NA SP-API credentials eksik

## Notlar

- **AWS Access Keys**: Her iki bölge için aynı AWS credentials kullanılır
- **SP-API Credentials**: NA ve EU bölgeleri için farklı olması gerekir
- Sidepanel özelliği değiştirilmedi, kullanıcı manuel marketplace seçebilir
- BSR data sadece US ve CA için mevcut
- EU marketplace'ler için ayrı BSR data gerekebilir
- Currency formatting tüm marketplace'ler için destekleniyor 