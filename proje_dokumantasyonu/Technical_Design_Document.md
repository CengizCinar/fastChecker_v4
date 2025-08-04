# Teknik Tasarım Dokümanı: FastChecker

**Sürüm:** 2.0
**Tarih:** 5 Ağustos 2025
**Yazar:** Gemini (AI Lead Developer)

---

## 1. Sistem Mimarisi ve Felsefesi

FastChecker, modern bir Chrome Uzantısı (Manifest V3) mimarisi üzerine inşa edilmiş, istemci-sunucu modelini benimseyen bir sistemdir. Temel tasarım felsefesi, **sorumlulukların net bir şekilde ayrılmasına** dayanır:

-   **Uzantı (Frontend):** Sadece kullanıcı arayüzünü (UI) sunmak ve kullanıcı etkileşimlerini yakalamaktan sorumludur. Hafif, hızlı ve duyarlı olmalıdır. Asla karmaşık iş mantığı veya ağır veri işleme içermemelidir.
-   **Arka Plan Betiği (`background.js`):** Uzantının farklı UI bileşenleri (Yan Panel, İçerik Betiği) ile harici servisler (Backend, SP-API) arasında bir **hava trafik kontrolörü (API Gateway)** görevi görür. Tüm harici iletişimi merkezileştirir ve yönetir.
-   **Harici Backend (Python Sunucusu):** Tüm ağır yükü omuzlayan iş gücüdür. Veri toplama (scraping), veri işleme, veri zenginleştirme ve harici API'lerle (SP-API) iletişim kurma gibi tüm karmaşık ve zaman alıcı işlemlerden sorumludur.

Bu ayrım, sistemi daha **modüler, bakımı kolay ve ölçeklenebilir** kılar.

### Mimari Şeması

```mermaid
graph TD
    subgraph "Tarayıcı (Chrome)"
        subgraph "FastChecker Uzantısı"
            A[Yan Panel UI<br>(sidepanel.js)]
            C[Ürün Sayfası UI<br>(content.js)]
            B[Arka Plan Betiği<br>(background.js)]
        end
    end

    subgraph "Harici Servisler"
        E[Python Backend<br>(app.py on Railway)]
        D[Amazon SP-API]
        F[WebSocket Sunucusu<br>(Glitch/Railway)]
    end

    A -- 1. Toplu ASIN Kontrol İsteği --> B
    C -- 2. Ürün Detayı İsteği --> B
    B -- 1a. SP-API İsteği --> D
    B -- 1b. Manuel Kontrol İsteği --> F
    B -- 2a. Backend İsteği --> E
    D -- 1a.i. Satılabilirlik Sonucu --> B
    F -- 1b.i. Manuel Sonuç --> B
    E -- 2a.i. Zenginleştirilmiş Ürün Verisi --> B
    B -- 1a.ii. Sonucu İlet --> A
    B -- 1b.ii. Sonucu İlet --> A
    B -- 2a.ii. Sonucu İlet --> C

    style A fill:#f9f,stroke:#333,stroke-width:2px
    style C fill:#f9f,stroke:#333,stroke-width:2px
    style B fill:#ccf,stroke:#333,stroke-width:2px
    style E fill:#cfc,stroke:#333,stroke-width:2px
```

## 2. Bileşenlerin Derinlemesine Analizi

### a. `manifest.json` (Uzantının Anayasası)

-   **`manifest_version`: 3:** Modern, daha güvenli ve performanslı Service Worker tabanlı arka plan betiklerini kullanır.
-   **`permissions`: `["storage", "sidePanel", "activeTab"]`:**
    -   `storage`: API ayarları ve manuel kontrol sonuçları gibi verileri `chrome.storage.local` üzerinde kalıcı olarak saklamak için kritik öneme sahiptir.
    -   `sidePanel`: Chrome'un yerleşik yan panel özelliğini kullanarak arayüz sunma izni.
-   **`host_permissions`:** Uzantının hangi alan adlarıyla iletişim kurabileceğini tanımlayan bir beyaz listedir. Bu, güvenliğin temel taşıdır. Sadece Amazon API'leri, Amazon ürün sayfaları ve kendi backend/WebSocket sunucularımıza erişim izni verilir.
-   **`background.service_worker`: `"background.js"`:** Uzantının kalıcı beyni. Tüm olayları dinler ve tepki verir.
-   **`content_scripts`:** Hangi sitelere (`*://*.amazon.com/*p/*`) hangi kodların (`content.js`, `product-ui.css`) enjekte edileceğini tanımlar. Bu, ürün sayfalarına UI eklememizi sağlar.
-   **`web_accessible_resources`:** `content.js` tarafından DOM'a eklenen HTML elementlerinin, uzantı paketindeki `product-ui.css` dosyasına erişebilmesini sağlar. Bu olmadan stiller uygulanamaz.

### b. `background.js` (Merkezi Koordinatör)

-   **Rolü:** Gelen tüm `chrome.runtime.onMessage` olaylarını dinleyen ve `request.action` parametresine göre ilgili işlevi çağıran bir yönlendiricidir.
-   **Asenkron Yönetim:** Tüm işlemler asenkrondur. `sendResponse` fonksiyonunu doğru bir şekilde yönetmek ve asenkron operasyonlar için `return true;` kullanmak, uzantının kilitlenmesini önler.
-   **API Ağ Geçidi:** `content.js` veya `sidepanel.js` **asla** doğrudan `fetch` ile harici bir API çağırmaz. Tüm istekler `background.js`'e bir mesaj olarak gönderilir ve `background.js` bu istekleri yapar. Bu, tüm ağ trafiğini tek bir yerden yönetmeyi, hata takibini kolaylaştırmayı ve gelecekte merkezi bir önbellekleme (caching) mekanizması eklemeyi mümkün kılar.
-   **WebSocket Yönetimi:** Manuel kontrol sonuçları için WebSocket bağlantısını kurar, hayatta tutar ve gelen mesajları işleyerek `sidepanel.js`'e iletir.

### c. `content.js` (Ürün Sayfası Cerrahı)

-   **Tetiklenme:** Amazon ürün detay sayfasının DOM'u yüklendiğinde çalışır.
-   **Veri Akışı:**
    1.  URL'den ASIN ve Pazar Yeri'ni çıkarır.
    2.  `chrome.runtime.sendMessage({ action: 'fetchProductDetails', ... })` ile `background.js`'den veri ister.
    3.  `chrome.runtime.onMessage` ile `background.js`'den gelen `displayProductDetails` eylemini dinler.
    4.  Gelen JSON verisiyle `updateUI` fonksiyonunu çağırarak arayüzü oluşturur ve doldurur.
-   **DOM Manipülasyonu:** `#rightCol` elementini hedef alarak, mevcut sayfa yapısını bozmadan arayüzü en üste ekler (`prepend`). `createUIContainer` içinde `existingUI` kontrolü, sayfa içi navigasyonlarda (örn. renk/boyut değiştirme) birden fazla panelin oluşmasını engeller.
-   **İzole Mantık:** Kendi içinde kâr hesaplama, kargo maliyeti hesaplama gibi UI'a özgü mantıkları barındırır. Ancak veri getirme mantığı tamamen `background.js`'e delege edilmiştir.

### d. `sidepanel.js` (Kontrol Paneli Yöneticisi)

-   **Sorumluluk:** API ayarlarını yönetme, toplu ASIN kontrolünü başlatma ve sonuçları gösterme.
-   **Veri Akışı:**
    1.  Kullanıcı "Kontrol Et" butonuna basar.
    2.  `checkAsins` fonksiyonu, `chrome.storage.local`'dan alınan ayarlarla birlikte ASIN listesini `background.js`'e `checkAsin` eylemiyle gönderir.
    3.  `chrome.runtime.onMessage` ile `asinResult` (tek bir ASIN sonucu) ve `manualResult` (WebSocket'ten gelen sonuç) eylemlerini dinler.
    4.  Gelen her sonuçla `addResultRow` ve `renderAllResults` fonksiyonlarını kullanarak arayüzü dinamik olarak günceller.
-   **Durum Yönetimi (`State Management`):** `isCheckInProgress`, `pendingManualChecks`, `isApiCheckDone` gibi bayraklarla mevcut işlemin durumunu takip eder. `checkIfAllDone` fonksiyonu, bu bayrakları kontrol ederek CSV indirme butonunu doğru zamanda gösterir.

### e. `backend_new/app.py` (Veri İşleme Motoru)

-   **Framework:** Flask (veya FastAPI), Python tabanlı hafif bir web sunucusu.
-   **Endpoint'ler:**
    -   `/get_product_details/<asin>`: `content.js` için ana veri kaynağı. Tek bir istekte birden çok Amazon SP-API çağrısını (ürün bilgisi, kısıtlamalar, ücretler, teklifler) birleştirir, veriyi işler (BSR analizi, boyut/ağırlık dönüşümü), zenginleştirir (kur oranları) ve tek bir temiz JSON olarak sunar.
    -   `/get_eu_business_prices/<asin>`: Avrupa arbitraj fırsatları için özel bir endpoint. Diğer pazar yerlerindeki B2B fiyatlarını ve MOQ'ları getirir.
-   **Credential Yönetimi:** `get_credentials_for_marketplace` fonksiyonu, gelen `marketplace` parametresine göre doğru SP-API kimlik bilgilerini (NA veya EU) seçer. Bu, çoklu bölge desteği için kritik öneme sahiptir.
-   **Önbellekleme (Caching):** BSR tabloları ve döviz kurları gibi sık değişmeyen ama getirilmesi maliyetli olan veriler için bellek içi (in-memory) önbellekleme mekanizmaları kullanır. Bu, performansı önemli ölçüde artırır ve harici servislere olan bağımlılığı azaltır.

## 3. Veri Modelleri (Data Models)

### Ürün Detayı JSON (Backend -> `content.js`)

```json
{
  "asin": "B08XYZ1234",
  "title": "Örnek Ürün Başlığı",
  "brand": "Örnek Marka",
  "imageUrl": "https://.../image.jpg",
  "dimensions": "10.0 x 5.0 x 2.0 cm",
  "packageWeight": "250 gr",
  "isSellable": true,
  "buyboxPrice": 29.99,
  "currencyCode": "USD",
  "referralFee": 4.50,
  "fbaFee": 3.75,
  "offers": [
    { "SellerId": "SELLER1", "IsFulfilledByAmazon": true, "ListingPrice": { "Amount": 29.99 } }
  ],
  "bsr_analysis": {
    "enhanced_display": "12k (Top 1%)"
  },
  "exchangeRates": {
    "EUR_USD": 1.08,
    "GBP_USD": 1.25
  },
  "eu_business_prices": [
      { "market": "DE", "price": 15.50, "currency": "EUR", "moq": 10 }
  ]
}
```

### ASIN Kontrol Sonucu (`background.js` -> `sidepanel.js`)

```json
{
    "asin": "B0C31QBVQ1",
    "status": "success", // veya "error"
    "sellable": false,
    "manual_check_pending": true, // Eğer onay gerekliyse
    "message": "Onay gerekli.",
    "details": {
        "brand": "Marka Adı",
        "title": "Ürün Başlığı",
        "reasons": [ { "reasonCode": "APPROVAL_REQUIRED" } ]
    }
}
```

## 4. Güvenlik Hususları

-   **SP-API Kimlik Bilgileri:** Asla kodun içine hard-coded yazılmaz. Yan panelde kullanıcı tarafından girilir ve `chrome.storage.local` içinde saklanır. Bu veriye sadece `background.js` erişebilir.
-   **Backend Güvenliği:** Backend sunucusu, ortam değişkenleri (environment variables) kullanarak hassas kimlik bilgilerini (SP-API tokenları, AWS anahtarları) yönetir. Kod tabanında hassas veri bulunmaz.
-   **Host İzinleri:** `manifest.json` içindeki `host_permissions`, uzantının sadece güvenilir ve gerekli alan adlarıyla iletişim kurmasını sağlayarak Cross-Site Scripting (XSS) ve veri sızıntısı risklerini en aza indirir.
