# FastChecker Projesi: API Entegrasyonları

Bu doküman, FastChecker uzantısının harici servislerle nasıl entegre olduğunu, hangi API'leri kullandığını ve bu entegrasyonların arkasındaki mantığı açıklar.

## 1. Amazon Selling Partner API (SP-API)

Bu, projenin en temel ve kritik entegrasyonudur. Yan Panel üzerinden yapılan toplu ASIN kontrolleri doğrudan SP-API'yi kullanır.

### a. Sorumlu Kod

-   **`sp-api-helper.js`**: SP-API ile tüm iletişimi yöneten `SPAPIHelper` sınıfını içerir. Bu sınıf, API çağrılarını daha basit ve yeniden kullanılabilir hale getirir.
-   **`background.js`**: `SPAPIHelper` sınıfını kullanarak asıl API isteklerini tetikler.

### b. Kimlik Doğrulama (Authentication)

SP-API, OAuth 2.0 tabanlı bir kimlik doğrulama mekanizması kullanır.

1.  **Refresh Token:** Kullanıcı, kendi Amazon Satıcı Hesabı'ndan aldığı uzun ömürlü bir "Refresh Token"ı uzantının ayarlarına girer.
2.  **Access Token Alınması:** Bir API isteği yapılacağı zaman, `sp-api-helper.js` içindeki `getAccessToken` fonksiyonu çalışır. Bu fonksiyon, `https://api.amazon.com/auth/o2/token` endpoint'ine Refresh Token, Client ID ve Client Secret ile bir POST isteği gönderir.
3.  **Geçici Access Token:** Amazon, bu isteğe karşılık olarak 1 saat geçerli olan bir "Access Token" döndürür.
4.  **Token Saklama:** `SPAPIHelper` sınıfı, bu Access Token'ı ve son kullanma zamanını bir değişkende saklar. Bir sonraki API isteğinde, eğer token hala geçerliyse, yeniden token istemek yerine mevcut olanı kullanır. Bu, gereksiz kimlik doğrulama isteklerini önleyerek performansı artırır.

### c. Kullanılan Endpoint

-   **`/listings/2021-08-01/restrictions`**: Bu endpoint, projenin temel "satılabilirlik" kontrolünü yapmak için kullanılır.
    -   **İstek Parametreleri:** `asin`, `sellerId`, `marketplaceIds`, `conditionType='new_new'`
    -   **Yanıt:** Eğer ürün satılabilirse, boş bir `restrictions` listesi döner. Eğer satılamazsa, bu liste içinde kısıtlama nedenlerini (`reasonCode`) içeren bir veya daha fazla nesne bulunur.
    -   **`if (restrictions.length === 0)`**: `sp-api-helper.js` içindeki bu basit kontrol, bir ürünün satılabilir olup olmadığını belirler.

## 2. FastChecker Python Backend API

Bu, Ürün Sayfası Arayüzü'ne veri sağlamak için proje dahilinde geliştirilmiş özel bir API'dir.

### a. Sorumlu Kod

-   **`backend_new/app.py`**: API sunucusunun kendisi.
-   **`background.js`**: Bu API'ye `fetch` ile istek yapan istemci.

### b. Endpoint'ler

-   **`GET /get_product_details/<asin>?marketplace=<market>`**
    -   **Amaç:** Bir ürün sayfasında gösterilecek tüm zenginleştirilmiş veriyi tek bir çağrıda toplamak.
    -   **Dönen Veri (Örnek JSON Yapısı):**
        ```json
        {
          "asin": "B08XYZ1234",
          "ean": "1234567890123",
          "title": "Örnek Ürün Başlığı",
          "brand": "Örnek Marka",
          "imageUrl": "https://.../image.jpg",
          "dimensions": "10 x 5 x 2 cm",
          "packageWeight": "250 gr",
          "isSellable": true,
          "buyboxPrice": 29.99,
          "currencyCode": "USD",
          "referralFee": 4.50,
          "fbaFee": 3.75,
          "offers": [
            { "SellerId": "SELLER1", "IsFulfilledByAmazon": true, "ListingPrice": { "Amount": 29.99, ... } },
            { "SellerId": "SELLER2", "IsFulfilledByAmazon": false, "ListingPrice": { "Amount": 30.50, ... } }
          ],
          "bsr_analysis": {
            "rank": 12345,
            "category": "Electronics",
            "enhanced_display": "12k (Top 1%)"
          },
          "exchangeRates": {
            "EUR_USD": 1.08,
            "GBP_USD": 1.25
          }
        }
        ```

-   **`GET /get_eu_business_prices/<asin>?markets=<markets>`**
    -   **Amaç:** Özellikle arbitraj fırsatlarını değerlendirmek için, bir ürünün diğer Avrupa pazar yerlerindeki B2B (Business-to-Business) fiyatlarını ve minimum sipariş miktarlarını (MOQ) getirmek.
    -   **Dönen Veri (Örnek JSON Yapısı):**
        ```json
        {
          "prices": [
            { "market": "DE", "price": 15.50, "currency": "EUR", "moq": 10 },
            { "market": "FR", "price": 16.00, "currency": "EUR", "moq": 5 }
          ]
        }
        ```

## 3. FastChecker WebSocket Sunucusu

Bu sunucu, SP-API'nin anında yanıt veremediği "Onay Gerekli" durumları için kullanılır.

### a. Sorumlu Kod

-   **`background.js`**: WebSocket istemcisi olarak görev yapar.

### b. İletişim Akışı

1.  **Bağlantı:** `background.js`, `connectWebSocket` fonksiyonu ile `wss://fastcheckerwebsocket-production.up.railway.app/` adresine kalıcı bir bağlantı kurar.
2.  **Gönderme (POST):** SP-API bir ürün için `APPROVAL_REQUIRED` döndürdüğünde, `background.js` bu ASIN'i aynı sunucunun `/mektup-at` endpoint'ine bir HTTP POST isteği ile gönderir.
3.  **Alma (onmessage):** Sunucu, arka planda bu ASIN'in durumunu çözdüğünde (bu işlem saniyeler veya dakikalar sürebilir), sonucu WebSocket bağlantısı üzerinden tüm bağlı istemcilere yayınlar.
4.  **`if (msg.type === 'manual-result')`**: `background.js`'deki `ws.onmessage` dinleyicisi, bu gelen mesajı yakalar. Eğer mesajın tipi `manual-result` ise, sonucu `chrome.storage.local`'a kaydeder ve `sidepanel.js`'in arayüzü güncellemesi için bir mesaj gönderir.
