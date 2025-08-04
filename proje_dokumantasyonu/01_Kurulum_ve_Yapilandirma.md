# FastChecker Projesi: Kurulum ve Yapılandırma

Bu doküman, FastChecker uzantısının geliştirme ortamına nasıl kurulacağını ve temel yapılandırma dosyalarının ne anlama geldiğini açıklar.

## 1. Geliştirme Ortamı Kurulumu

Uzantıyı yerel makinede test etmek ve geliştirmek için aşağıdaki adımlar izlenmelidir:

1.  **Google Chrome:** Güncel bir Google Chrome tarayıcısı kurulu olmalıdır.
2.  **Uzantıyı Yükleme:**
    *   Chrome'u açın ve `chrome://extensions` adresine gidin.
    *   Sağ üst köşedeki "Geliştirici modu" (Developer mode) anahtarını aktif hale getirin.
    *   "Paketlenmemiş öğe yükle" (Load unpacked) butonuna tıklayın.
    *   Projenin ana dizinini (`/Users/cengizcinar/Downloads/FastChecker_v4/fastChecker_v4 copy`) seçin.
3.  **Backend'i Çalıştırma (Opsiyonel ama Önemli):**
    *   Ürün Sayfası Arayüzü'nün tam işlevsellikle çalışması için Python backend'inin çalışır durumda olması gerekir.
    *   Terminalde `backend_new` klasörüne gidin: `cd /Users/cengizcinar/Downloads/FastChecker_v4/fastChecker_v4 copy/backend_new`
    *   Gerekli Python kütüphanelerini yükleyin: `pip install -r requirements.txt` (varsa)
    *   Uygulamayı başlatın: `python app.py`

Kurulum tamamlandığında, Chrome'un uzantılar çubuğunda FastChecker ikonu görünecektir.

## 2. Ana Yapılandırma Dosyası: `manifest.json`

Bu dosya, Chrome uzantısının kalbidir ve tüm temel tanımlamaları, izinleri ve bileşenleri içerir.

```json
{
   "manifest_version": 3,
   "name": "newChecker",
   "version": "1.1.0",
   "description": "Amazon SP API ASIN Checker and Product Detailer",
   "author": "FastChecker Team",
   "permissions": [
      "storage",
      "sidePanel",
      "activeTab"
   ],
   "host_permissions": [
      "https://sellingpartnerapi-na.amazon.com/*",
      "https://sellingpartnerapi-eu.amazon.com/*",
      "https://sellingpartnerapi-fe.amazon.com/*",
      "https://*.amazon.com/*",
      "https://fastcheckerwebsocket.glitch.me/*" // WebSocket sunucusu adresi
   ],
   "background": {
      "service_worker": "background.js"
   },
   "side_panel": {
      "default_path": "sidepanel/sidepanel.html"
   },
   "action": {
      "default_title": "FastChecker"
   },
   "web_accessible_resources": [
      {
         "resources": ["product-ui.css"],
         "matches": ["<all_urls>"]
      }
   ],
   "content_scripts": [
      {
         "matches": ["*://*.amazon.com/*p/*", ...], // Tüm Amazon ürün sayfaları
         "js": ["content.js"],
         "css": ["product-ui.css"]
      }
   ],
   "icons": { ... }
}
```

### `manifest.json` Alanlarının Açıklamaları:

-   **`manifest_version`**: 3. Chrome'un modern uzantı platformunu kullandığımızı belirtir.
-   **`permissions`**: Uzantının ihtiyaç duyduğu temel Chrome API izinleri.
    -   `storage`: SP-API ayarları gibi verileri kullanıcının bilgisayarında saklamak için.
    -   `sidePanel`: Tarayıcının yan panelini kullanabilmek için.
    -   `activeTab`: Aktif sekme hakkında bilgi almak için (ancak proje genelinde daha çok mesajlaşma kullanılır).
-   **`host_permissions`**: Uzantının hangi web siteleriyle iletişim kurabileceğini tanımlar. Bu, güvenlik için kritik bir ayardır.
    -   `sellingpartnerapi-*.amazon.com`: Amazon SP-API sunucularına erişim için.
    -   `*.amazon.com`: Tüm Amazon alan adlarındaki ürün sayfalarına `content.js` enjekte edebilmek için.
    -   `fastcheckerwebsocket.glitch.me`: Manuel ASIN kontrol sonuçlarını almak için WebSocket sunucusuna erişim için.
-   **`background`**: Arka plan betiğimizin `background.js` olduğunu belirtir. Bu betik, uzantının beyin fonksiyonlarını yerine getirir.
-   **`side_panel`**: Yan panelin içeriğinin `sidepanel/sidepanel.html` dosyasından yükleneceğini tanımlar.
-   **`action`**: Tarayıcı araç çubuğundaki uzantı ikonuna tıklandığında ne olacağını belirtir (bu projede yan paneli açar).
-   **`web_accessible_resources`**: Hangi dosyaların web sayfaları tarafından erişilebilir olduğunu tanımlar. `product-ui.css` dosyasının `content.js` tarafından enjekte edilen HTML elementlerini stilize edebilmesi için bu gereklidir.
-   **`content_scripts`**: Hangi web sitelerine hangi betiklerin enjekte edileceğini tanımlar. `content.js` ve `product-ui.css` dosyaları, `matches` kalıbıyla eşleşen tüm Amazon ürün sayfalarına enjekte edilir.

## 3. Diğer Yapılandırma Dosyaları

-   **`GEMINI.md`**: Bu dosya, yapay zeka (Gemini) ajanına projeyi nasıl ele alması gerektiği konusunda talimatlar verir. Özellikle Yan Panel ve Ürün Sayfası UI'ları arasındaki mantıksal ayrımın korunmasını vurgular.
-   **`requirements.txt`**: `backend_new` klasörü içindeki bu dosya, Python backend'inin çalışması için gerekli olan kütüphaneleri listeler (`pip install -r requirements.txt` komutu ile yüklenirler).
