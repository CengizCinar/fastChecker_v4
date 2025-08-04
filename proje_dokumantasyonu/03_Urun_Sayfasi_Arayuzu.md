# FastChecker Projesi: Ürün Sayfası Arayüzü

Bu doküman, Amazon ürün sayfalarına enjekte edilen kullanıcı arayüzünün (`Browser UI` veya `Content Script`) işlevlerini, mantığını ve kod yapısını detaylandırır.

## 1. Genel Bakış ve Sorumluluklar

Ürün Sayfası Arayüzü, kullanıcının bir Amazon ürün detay sayfasını ziyaret ettiğinde, sayfanın sağ tarafındaki (`#rightCol`) alana dinamik olarak eklenen bir bilgi panelidir. Temel amacı, satıcının ürünle ilgili anlık ve derinlemesine bir analiz yapmasını sağlamaktır.

**Ana Sorumlulukları:**

-   **Veri Gösterimi:** Ziyaret edilen ürünün ASIN, EAN, marka, boyut, ağırlık gibi temel bilgilerini göstermek.
-   **Satılabilirlik Durumu:** Ürünün satıcının hesabında satılıp satılamayacağını belirtmek.
-   **Kar Hesaplayıcı:** Kullanıcının maliyet ve satış fiyatı girerek potansiyel kar, ROI ve başa baş noktasını anında hesaplamasını sağlamak.
-   **Kargo Maliyeti Hesaplama:** Kullanıcının önceden tanımladığı koli boyutlarına ve ağırlıklarına göre birim başına düşen kargo maliyetini hesaplamak.
-   **Rakip Analizi:** Üründeki diğer FBA ve FBM satıcılarını ve fiyatlarını listelemek.
-   **Avrupa Fiyat Karşılaştırması:** Ürünün diğer Avrupa Amazon pazar yerlerindeki (DE, FR, IT, ES) fiyatlarını göstermek.
-   **BSR Analizi:** Ürünün En Çok Satanlar Sıralaması (Best Sellers Rank) verisini ve kategori içindeki yüzdelik dilimini göstermek.

## 2. Dosya Yapısı

Bu arayüzle ilgili dosyalar şunlardır:

-   `content.js`: Arayüzü oluşturan, yöneten ve tüm mantığı içeren ana JavaScript dosyası. Amazon ürün sayfalarına enjekte edilir.
-   `product-ui.css`: Arayüzün tüm stilini tanımlayan CSS dosyası.
-   `background.js`: `content.js`'den gelen veri isteklerini alıp Python backend'ine yönlendiren ve sonuçları geri ileten aracı.
-   `backend_new/app.py`: Gerekli tüm verileri toplayıp işleyen ve `content.js`'in kullanıma hazır hale getiren Python sunucu uygulaması.

## 3. İşlevsel Akış: Bir Ürün Sayfası Nasıl Analiz Edilir?

1.  **Sayfa Yüklenir ve `content.js` Tetiklenir:**
    -   Kullanıcı bir Amazon ürün sayfasına (`/dp/ASIN`) girer.
    -   `manifest.json` kuralları gereği, `content.js` ve `product-ui.css` bu sayfaya otomatik olarak enjekte edilir.
    -   `content.js`'in en altındaki IIFE (Immediately Invoked Function Expression) anında çalışır.

2.  **ASIN ve Pazar Yeri Tespiti:**
    -   `getAsinFromUrl()` ve `getMarketplaceFromUrl()` fonksiyonları, sayfanın URL'sini analiz ederek mevcut ASIN'i ve pazar yerini (örn: 'US', 'DE') tespit eder.

3.  **`content.js`'den `background.js`'e Mesaj Gönderilir:**
    -   `content.js`, `chrome.runtime.sendMessage` kullanarak `background.js`'e iki ana istek gönderir:
        1.  `action: 'fetchProductDetails'`: Ürünün ana verilerini (başlık, marka, ücretler, satıcılar vb.) istemek için.
        2.  `action: 'fetchEuMarketPrices'`: Ürünün Avrupa fiyatlarını istemek için.

4.  **`background.js` İstekleri Backend'e Yönlendirir:**
    -   `background.js`, bu istekleri alır ve `fetch` API'sini kullanarak Python backend'indeki ilgili endpoint'lere yönlendirir:
        -   `https://web-production-e38b7.up.railway.app/get_product_details/...`
        -   `https://web-production-e38b7.up.railway.app/get_eu_business_prices/...`

5.  **Python Backend Verileri Toplar ve İşler:**
    -   Backend, Amazon'dan (muhtemelen web scraping veya kendi API çağrıları ile) ham verileri toplar. Bu verileri işler, BSR analizi yapar, kur oranlarını ekler ve tek, temiz bir JSON nesnesi olarak paketler.

6.  **Veriler `content.js`'e Geri Döner:**
    -   `background.js`, backend'den gelen JSON yanıtını alır ve `chrome.tabs.sendMessage` ile veriyi orijinal isteği yapan `content.js` betiğine geri gönderir.

7.  **Arayüz Oluşturulur ve Doldurulur (`updateUI`):**
    -   `content.js`'deki `onMessage` dinleyicisi veriyi yakalar.
    -   `updateUI` fonksiyonu, gelen JSON verisini kullanarak panelin HTML içeriğini dinamik olarak oluşturur. Tüm alanlar (ASIN, marka, boyutlar, vb.) bu verilerle doldurulur.
    -   `renderEuMarketPrices` fonksiyonu, Avrupa fiyatları verisi geldiğinde ilgili bölümü doldurur.

## 4. Önemli `if` Koşulları ve Mantıklar (`content.js`)

-   **`createUIContainer()` içinde:**
    -   `if (existingUI)`: Sayfada zaten bir FastChecker paneli olup olmadığını kontrol eder. Varsa, eskisini kaldırıp yenisini ekleyerek çift arayüz oluşmasını engeller.
    -   `if (rightCol)`: Panelin ekleneceği `#rightCol` elementinin sayfada var olup olmadığını kontrol eder. Bu, Amazon'un sayfa yapısını değiştirmesi durumunda uzantının hata vermesini önler.

-   **`calculateAndDisplayShipping()` içinde:**
    -   Bu fonksiyon, kargo hesaplaması için gerekli tüm verilerin (kullanıcı ayarları, ürün boyutları, ürün ağırlığı) mevcut olup olmadığını kontrol eden çok sayıda `if` koşulu içerir. Herhangi bir veri eksikse, hesaplama yapmaz ve ilgili alanı boş bırakır.
    -   `if (itemDims[0] > pkgDims[0] ...)`: Ürünün boyutlarının, kullanıcının tanımladığı koli boyutlarından büyük olup olmadığını kontrol eder. Eğer büyükse, "Ürün koliye sığmıyor" mesajı gösterir.

-   **`updateCostInput()` içinde:**
    -   Bu fonksiyon, hem birim başına kargo maliyetinin (`calculatedCostPerItem`) hem de en düşük Avrupa fiyatının (`lowestEuPrice`) hesaplanıp hesaplanmadığını kontrol eder. Her ikisi de mevcut olduğunda, bu iki değeri ve kur oranlarını kullanarak nihai maliyeti hesaplar ve "Cost" alanını otomatik olarak günceller.

-   **`calculateProfit()` içinde:**
    -   `if (profit > 0)` ve `if (roi > 0)`: Hesaplanan kar ve ROI değerlerinin pozitif veya negatif olmasına göre sonuçlara `positive` veya `negative` CSS sınıfları ekler. Bu, sonuçların yeşil (karlı) veya kırmızı (zararda) renkte görünmesini sağlar.

## 5. Ayarlar Arayüzü (`Settings View`)

-   Kullanıcı, ana paneldeki dişli (⚙️) ikonuna tıklayarak Ayarlar görünümüne geçebilir.
-   Bu görünüm, `renderSettingsView` fonksiyonu tarafından oluşturulur ve kullanıcının kargo hesaplamaları için koli boyutlarını, maksimum ağırlığı ve kargo ücretini girmesini sağlar.
-   Girilen bu ayarlar, `saveShippingSettings` fonksiyonu ile `chrome.storage.local`'a kaydedilir ve kargo maliyeti hesaplamalarında kullanılır.
