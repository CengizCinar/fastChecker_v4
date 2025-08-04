# FastChecker Projesi: Yan Panel Arayüzü

Bu doküman, uzantının yan panel arayüzünün (`Side Panel UI`) işlevlerini, mantığını ve kod yapısını detaylandırır.

## 1. Genel Bakış ve Sorumluluklar

Yan Panel, kullanıcının FastChecker ile doğrudan etkileşim kurduğu ana kontrol merkezidir. Temel sorumlulukları şunlardır:

-   **API Yapılandırması:** Kullanıcının Amazon SP-API'ye erişim için gerekli olan kimlik bilgilerini (Refresh Token, Client ID, vb.) girmesini ve kaydetmesini sağlamak.
-   **Toplu ASIN Kontrolü:** Kullanıcının bir veya daha fazla ASIN'i bir metin alanına girerek bu ürünlerin kendi satıcı hesabında satılıp satılamayacağını kontrol etmesini sağlamak.
-   **Sonuçların Gösterimi:** API'den gelen ve WebSocket üzerinden güncellenen kontrol sonuçlarını kullanıcıya gerçek zamanlı olarak listelemek.
-   **Veri İndirme:** Kontrol edilen tüm ASIN'lerin sonuçlarını bir CSV dosyası olarak indirme imkanı sunmak.

## 2. Dosya Yapısı

Yan Panel ile ilgili tüm dosyalar `sidepanel/` klasörü altında ve ana dizindeki `sp-api-helper.js` ile `background.js` dosyalarında bulunur:

-   `sidepanel/sidepanel.html`: Arayüzün HTML iskeleti.
-   `sidepanel/sidepanel.css`: Arayüzün stil dosyası.
-   `sidepanel/sidepanel.js`: Arayüzün tüm dinamik işlevlerini ve mantığını içeren ana JavaScript dosyası.
-   `sp-api-helper.js`: Amazon SP-API ile iletişimi kolaylaştıran bir yardımcı sınıf. `background.js` tarafından kullanılır.
-   `background.js`: Yan panelden gelen istekleri alıp işleyen ve SP-API'ye yönlendiren arka plan betiği.

## 3. İşlevsel Akış: Bir ASIN Kontrolü Nasıl Çalışır?

1.  **Kullanıcı Bilgileri Girer:**
    -   Kullanıcı, "SP-API Ayarları" bölümüne kimlik bilgilerini girer ve "Ayarları Kaydet" butonuna tıklar.
    -   `sidepanel.js` içindeki `saveApiSettings` fonksiyonu tetiklenir. Bu fonksiyon, girilen verileri `chrome.storage.local.set` ile güvenli bir şekilde tarayıcının yerel deposuna kaydeder.

2.  **Kullanıcı ASIN'leri Girer ve Kontrolü Başlatır:**
    -   Kullanıcı, "ASIN Kontrol" bölümündeki metin alanına virgülle ayrılmış ASIN'leri girer ve "Kontrol Et" butonuna tıklar.
    -   `sidepanel.js` içindeki `checkAsins` fonksiyonu çalışır.

3.  **`sidepanel.js`'den `background.js`'e Mesaj Gönderilir:**
    -   `checkAsins` fonksiyonu, `chrome.runtime.sendMessage` kullanarak `background.js`'e bir mesaj gönderir. Bu mesaj şunları içerir:
        -   `action: 'checkAsin'`
        -   `data`: ASIN listesi ve `chrome.storage.local`'dan okunan API kimlik bilgileri.

4.  **`background.js` İsteği İşler:**
    -   `background.js`'deki `onMessage` dinleyicisi bu isteği yakalar.
    -   `handleAsinCheck` fonksiyonunu çağırır.
    -   Bu fonksiyon, bir döngü içinde her bir ASIN için `SPAPIHelper` sınıfının `checkASINSellability` metodunu çağırır.

5.  **SP-API ile İletişim:**
    -   `sp-api-helper.js` içindeki `checkASINSellability` metodu, önce bir `accessToken` alır, ardından Amazon'un `/listings/2021-08-01/restrictions` endpoint'ine bir istek gönderir.

6.  **Sonuçların Geri Gönderilmesi:**
    -   Her bir ASIN için API'den sonuç geldikçe, `background.js` bu sonucu `chrome.runtime.sendMessage` ile `sidepanel.js`'e geri gönderir (`action: 'asinResult'`).

7.  **Arayüzün Güncellenmesi:**
    -   `sidepanel.js`'deki `onMessage` dinleyicisi `asinResult` mesajını yakalar.
    -   `addResultRow` fonksiyonu, gelen sonucu `results` dizisine ekler ve `renderAllResults` ile arayüzü güncelleyerek yeni sonucu listenin en üstünde gösterir.

## 4. Önemli `if` Koşulları ve Mantıklar (`sidepanel.js`)

-   **`checkAsins()` içinde:**
    -   `if (!asinInput)`: Kullanıcının ASIN girip girmediğini kontrol eder. Boşsa hata verir.
    -   `if (!result.apiSettings?.refreshToken ...)`: Kullanıcının API ayarlarını kaydedip kaydetmediğini kontrol eder. Kaydetmemişse hata verir.

-   **`createResultRow(result)` içinde:**
    -   Bu fonksiyon, bir sonucun durumuna göre (`sellable`, `error`, `manual_check_pending`, `manual_status`) hangi metnin ve hangi CSS sınıfının (`eligible`, `not-eligible`, `checking`, `error`) uygulanacağını belirleyen bir `if/else if/else` bloğu içerir. Bu, sonuçların renkli ve anlaşılır bir şekilde gösterilmesini sağlar.

-   **`handleManualResult(result)` içinde:**
    -   `if (resultIndex !== -1)`: WebSocket'ten gelen bir manuel sonucun, zaten listede var olan bir ASIN'e ait olup olmadığını kontrol eder. Eğer varsa, mevcut öğeyi günceller ve listenin en üstüne taşır.

-   **`checkIfAllDone()` içinde:**
    -   `if (this.isApiCheckDone && this.pendingManualChecks === 0 ...)`: Hem ilk API kontrollerinin bittiğini hem de beklenen manuel kontrol sayısının sıfıra ulaştığını kontrol eder. Bu koşul sağlandığında, "Sonuçları CSV Olarak İndir" butonu görünür hale gelir.

## 5. WebSocket Entegrasyonu (Manuel Kontrol)

-   Eğer SP-API bir ürün için `APPROVAL_REQUIRED` (Onay Gerekli) durumunu döndürürse, bu ürünün durumu belirsizdir ve manuel bir kontrol gerektirir.
-   Bu durumda, `background.js`, bu ASIN'i WebSocket sunucusuna (`wss://fastcheckerwebsocket-production.up.railway.app/mektup-at`) bir POST isteği ile gönderir.
-   WebSocket sunucusu, bu ASIN için arka planda (muhtemelen başka bir otomasyon veya insan müdahalesi ile) bir kontrol yapar.
-   Sonuç hazır olduğunda, sunucu bu sonucu bağlı olan tüm istemcilere (yani açık olan tüm FastChecker uzantılarına) bir WebSocket mesajı (`type: 'manual-result'`) ile gönderir.
-   `background.js` bu mesajı alır, `chrome.storage.local`'a kaydeder ve `sidepanel.js`'e iletir. `sidepanel.js` de ilgili ASIN'in durumunu arayüzde günceller.
