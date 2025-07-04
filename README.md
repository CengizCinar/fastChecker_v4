# FastChecker Teknik README

## Projeye Genel Bakış

FastChecker, Amazon satıcıları için tasarlanmış bir tarayıcı uzantısı ve ona eşlik eden bir arka uç servisidir. Uzantı, Amazon ürün sayfalarına doğrudan entegre olarak ve toplu ASIN kontrolü için bir yan panel sağlayarak, bir ürünün satılabilirlik durumunu, potansiyel kârını ve diğer önemli metrikleri hızlı bir şekilde değerlendirmelerine olanak tanır.

Bu README, projenin teknik mimarisini, bileşenlerini ve gelecekteki geliştirme potansiyelini anlamak için bir rehber olarak hizmet vermektedir.

## Temel Özellikler

*   **Anında Ürün Analizi:** Amazon ürün sayfalarında, ürünün satılabilir olup olmadığını, Buy Box fiyatını, tahmini ücretleri ve net kârı gösteren bir UI enjekte eder.
*   **Toplu ASIN Kontrolü:** Yan panel aracılığıyla birden fazla ASIN'in satılabilirlik durumunu aynı anda kontrol etme.
*   **Ayrıntılı Bilgiler:** Selling Partner API'den alınan kapsamlı veriler:
    *   Katalog bilgileri (başlık, marka, resim, EAN, boyutlar)
    *   Satış kısıtlamaları
    *   Teklifler ve Buy Box kazananı
    *   FBA ücret tahminleri ve net kâr analizi
*   **Maliyet Hesaplayıcı:** Nihai kârı belirlemek için ürün maliyetini girme yeteneği.
*   **CSV Olarak Dışa Aktarma:** Toplu kontrol sonuçlarını CSV formatında indirme.
*   **Çok Dilli Destek:** İngilizce ve Türkçe dillerini destekler.

## Teknik Mimari

FastChecker, iki ana bileşenden oluşan bir istemci-sunucu mimarisine sahiptir:

1.  **Tarayıcı Uzantısı (Ön Uç):** Kullanıcının tarayıcısında çalışan ve kullanıcı arayüzünü sağlayan bölüm.
2.  **Arka Uç Servisi (Backend):** Amazon Selling Partner API ile iletişimi yöneten, verileri işleyen ve uzantıya API hizmeti sunan ayrı bir sunucu tarafı uygulama.

### 1. Tarayıcı Uzantısı (Ön Uç)

*   **Teknolojiler:** HTML, CSS, JavaScript
*   **Yapı:**
    *   **`manifest.json`**: Uzantının temel yapılandırması, izinleri ve komut dosyalarını tanımlar.
    *   **`content.js`**: Amazon ürün sayfalarına enjekte edilir. Sayfadan ASIN'i çıkarır, arka plana veri getirme isteği gönderir ve sonuçları görüntülemek için bir UI oluşturur.
    *   **`background.js`**: Arka plan hizmet çalışanı. `content.js` ve `sidepanel.js`'den gelen mesajları dinler, arka uç servisine API istekleri yapar ve sonuçları geri gönderir.
    *   **`sidepanel.html`, `sidepanel.css`, `sidepanel.js`**: Toplu ASIN kontrolü, API ayarları ve sonuçların görüntülenmesi için kullanıcı arayüzünü oluşturur.
    *   **`sp-api-helper.js`**: Arka uç API'sine yapılan çağrıları basitleştirmek için bir yardımcı betik.
    *   **`product-ui.css`**: Ürün sayfasına enjekte edilen UI'nin stilleri.

### 2. Arka Uç Servisi (Backend)

*   **Konum:** Projenin `backend_new/` dizininde bulunur.
*   **Teknolojiler:** Python, Flask, `sp-api` kütüphanesi
*   **Yapı:**
    *   **`app.py`**: Flask uygulamasının ana dosyası.
        *   `/get_product_details/<string:asin>` adında bir API uç noktası sunar.
        *   Bu uç nokta, bir ASIN alır ve `sp-api` kütüphanesini kullanarak Selling Partner API'den ürünle ilgili tüm ayrıntıları (katalog, kısıtlamalar, teklifler, ücretler) alır.
        *   İşlenmiş verileri JSON formatında tarayıcı uzantısına geri döndürür.
    *   **`requirements.txt`**: Python bağımlılıklarını listeler.
    *   **`Procfile`**: Sunucunun nasıl başlatılacağını tanımlar (örneğin, Gunicorn ile).
    *   **`runtime.txt`**: Kullanılan Python versiyonunu belirtir.
    *   **`railway.toml`**: Railway platformuna özel dağıtım yapılandırmasını içerir.
    *   **`bsr_scraper.py`**: BSR verilerini çeken yardımcı modül.
    *   **`config.json`**: Yalnızca yerel geliştirme için kullanılan, hassas bilgileri içeren yapılandırma dosyası. **Üretim ortamında ortam değişkenleri kullanılır.**

## Kurulum ve Çalıştırma

### Tarayıcı Uzantısı (Son Kullanıcı İçin)

1.  Google Chrome'da `chrome://extensions` adresine gidin.
2.  "Geliştirici modunu" etkinleştirin.
3.  "Paketlenmemiş öğe yükle"yi tıklayın ve bu projenin ana dizinini seçin.
4.  Uzantı, tarayıcı araç çubuğunuza eklenecektir.

### Arka Uç Servisi (Geliştiriciler ve Dağıtım İçin)

Arka uç servisi, ayrı bir sunucu ortamında (örneğin Railway, Heroku, AWS) dağıtılmak üzere tasarlanmıştır. Son kullanıcıların bu servisi yerel olarak kurmasına veya çalıştırmasına gerek yoktur.

**Yerel Geliştirme İçin:**

1.  `backend_new` dizinine gidin: `cd backend_new`
2.  Gerekli paketleri yükleyin: `pip install -r requirements.txt`
3.  `backend_new/config.json` dosyasını kendi SP-API kimlik bilgilerinizle doldurun.
4.  Sunucuyu başlatın: `python app.py`
5.  Sunucu, `http://127.0.0.1:5003` adresinde çalışmaya başlayacaktır.

**Üretim Ortamında Dağıtım İçin:**

Railway gibi bir platform kullanarak dağıtım yapılması önerilir. Ortam değişkenleri (`AMAZON_REFRESH_TOKEN`, `AMAZON_LWA_APP_ID`, `AMAZON_LWA_CLIENT_SECRET`, `AMAZON_SELLER_ID`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`) doğru şekilde ayarlanmalıdır.

## Gelecekteki Geliştirmeler ve Olasılıklar

Bu proje, Amazon satıcıları için güçlü bir araç olma potansiyeline sahiptir. İşte gelecekteki geliştirmeler için bazı fikirler:

### Kısa Vade

*   **Hata Yönetimini İyileştirme:** API'den gelen hataları daha ayrıntılı ve kullanıcı dostu bir şekilde gösterme.
*   **Kullanıcı Arayüzünü Geliştirme:** Daha modern ve sezgisel bir kullanıcı arayüzü tasarlama. Belki bir grafik kütüphanesi (örn. Chart.js) ile kâr ve maliyet analizini görselleştirme.
*   **Daha Fazla Veri Noktası:** SP-API'den daha fazla veri çekme (örneğin, satış sıralaması geçmişi, envanter seviyeleri, reklam metrikleri).

### Orta Vade

*   **Tarihsel Veri Takibi:** Ürünlerin fiyat, satış sıralaması ve satılabilirlik durumu gibi metriklerini zaman içinde takip etme ve bu verileri grafiklerle görselleştirme.
*   **Rakip Analizi:** Bir ürün listesindeki diğer satıcılar hakkında daha ayrıntılı bilgi sağlama (örneğin, stok seviyeleri, değerlendirme sayıları).
*   **Otomatik Fiyatlandırma Önerileri:** Kâr hedeflerine ve rekabete dayalı olarak otomatik fiyatlandırma önerileri sunma.
*   **Envanter Yönetimi Entegrasyonu:** Kullanıcının kendi envanterini yönetmesine ve yeniden stoklama önerileri almasına olanak tanıma.

### Uzun Vade

*   **Makine Öğrenmesi Modelleri:**
    *   **Satış Tahmini:** Tarihsel verileri ve pazar trendlerini kullanarak gelecekteki satışları tahmin etme.
    *   **Fiyat Optimizasyonu:** Kârı maksimize etmek için en uygun fiyat noktasını belirleme.
    *   **Trend Analizi:** Yükselen ürünleri ve nişleri belirleme.
*   **Çoklu Pazar Yeri Desteğini Genişletme:** Tüm Amazon pazar yerlerinde sorunsuz çalışacak şekilde altyapıyı geliştirme.
*   **Tam Teşekküllü Bir SaaS Platformuna Dönüştürme:** Sadece bir tarayıcı uzantısı olmaktan çıkıp, kullanıcıların tüm Amazon işlerini yönetebilecekleri kapsamlı bir web uygulaması (SaaS) haline getirme.

Bu README, projenin mevcut durumunu ve potansiyelini yansıtmaktadır. Kod tabanını daha da keşfederek ve yukarıdaki fikirleri geliştirerek, FastChecker'ı Amazon satıcıları için vazgeçilmez bir araç haline getirebilirsiniz.