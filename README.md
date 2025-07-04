# FastChecker Teknik README

## Projeye Genel Bakış

FastChecker, Amazon satıcıları için tasarlanmış bir tarayıcı uzantısıdır. Amazon ürün sayfalarına doğrudan entegre olarak ve toplu ASIN kontrolü için bir yan panel sağlayarak, bir ürünün satılabilirlik durumunu, potansiyel kârını ve diğer önemli metrikleri hızlı bir şekilde değerlendirmelerine olanak tanır.

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

FastChecker, üç ana bileşenden oluşan bir istemci-sunucu mimarisine sahiptir:

1.  **Tarayıcı Uzantısı (Ön Uç):** Kullanıcının tarayıcısında çalışan ve kullanıcı arayüzünü sağlayan bölüm.
2.  **Arka Uç Sunucusu:** Amazon Selling Partner API ile iletişimi yöneten ve verileri işleyen sunucu tarafı uygulama.
3.  **Amazon Selling Partner (SP) API:** Ürün ve satıcı verilerinin kaynağı.

### 1. Tarayıcı Uzantısı (Ön Uç)

*   **Teknolojiler:** HTML, CSS, JavaScript (jQuery yok)
*   **Yapı:**
    *   **`manifest.json`**: Uzantının temel yapılandırması, izinleri ve komut dosyalarını tanımlar.
    *   **`content.js`**: Amazon ürün sayfalarına enjekte edilir. Sayfadan ASIN'i çıkarır, arka plana veri getirme isteği gönderir ve sonuçları görüntülemek için bir UI oluşturur.
    *   **`background.js`**: Arka plan hizmet çalışanı. `content.js` ve `sidepanel.js`'den gelen mesajları dinler, arka uç sunucusuna API istekleri yapar ve sonuçları geri gönderir.
    *   **`sidepanel.html`, `sidepanel.css`, `sidepanel.js`**: Toplu ASIN kontrolü, API ayarları ve sonuçların görüntülenmesi için kullanıcı arayüzünü oluşturur.
    *   **`sp-api-helper.js`**: (Varsayım) Arka uç API'sine yapılan çağrıları basitleştirmek için bir yardımcı betik.
    *   **`product-ui.css`**: Ürün sayfasına enjekte edilen UI'nin stilleri.

### 2. Arka Uç Sunucusu

*   **Teknolojiler:** Python, Flask, `sp-api` kütüphanesi
*   **Yapı:**
    *   **`app.py`**: Flask uygulamasının ana dosyası.
        *   `/get_product_details/<string:asin>` adında tek bir API uç noktası sunar.
        *   Bu uç nokta, bir ASIN alır ve `sp-api` kütüphanesini kullanarak Selling Partner API'den ürünle ilgili tüm ayrıntıları (katalog, kısıtlamalar, teklifler, ücretler) alır.
        *   İşlenmiş verileri JSON formatında tarayıcı uzantısına geri döndürür.
    *   **`config.json`**: SP-API kimlik bilgilerini, satıcı kimliğini ve pazar yerini depolar. **Not:** Bu dosya hassas bilgiler içerir ve asla genel bir depoya kaydedilmemelidir.
    *   **`venv`**: Python sanal ortamı.

## Kurulum ve Çalıştırma

### Ön Uç (Tarayıcı Uzantısı)

1.  Google Chrome'da `chrome://extensions` adresine gidin.
2.  "Geliştirici modunu" etkinleştirin.
3.  "Paketlenmemiş öğe yükle"yi tıklayın ve `FastChecker-main` dizinini seçin.
4.  Uzantı, tarayıcı araç çubuğunuza eklenecektir.

### Arka Uç (Yerel Sunucu)

1.  Python 3'ün kurulu olduğundan emin olun.
2.  `backend` dizinine gidin: `cd backend`
3.  Sanal ortamı etkinleştirin: `source venv/bin/activate` (macOS/Linux) veya `venv\Scripts\activate` (Windows).
4.  Gerekli paketleri yükleyin: `pip install -r requirements.txt` (Not: `requirements.txt` dosyası eksik, bu yüzden `pip install Flask flask-cors sp-api` komutu kullanılmalıdır).
5.  `backend/config.json` dosyasını kendi SP-API kimlik bilgilerinizle doldurun.
6.  Sunucuyu başlatın: `python app.py`
7.  Sunucu, `http://127.0.0.1:5003` adresinde çalışmaya başlayacaktır.

## Gelecekteki Geliştirmeler ve Olasılıklar

Bu proje, Amazon satıcıları için güçlü bir araç olma potansiyeline sahiptir. İşte gelecekteki geliştirmeler için bazı fikirler:

### Kısa Vade

*   **Hata Yönetimini İyileştirme:** API'den gelen hataları daha ayrıntılı ve kullanıcı dostu bir şekilde gösterme.
*   **Kullanıcı Arayüzünü Geliştirme:** Daha modern ve sezgisel bir kullanıcı arayüzü tasarlama. Belki bir grafik kütüphanesi (örn. Chart.js) ile kâr ve maliyet analizini görselleştirme.
*   **Daha Fazla Veri Noktası:** SP-API'den daha fazla veri çekme (örneğin, satış sıralaması geçmişi, envanter seviyeleri, reklam metrikleri).
*   **`requirements.txt` Dosyası:** Arka uç bağımlılıklarının kolay kurulumu için bir `requirements.txt` dosyası oluşturma.

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
*   **Tam Teşekküllü Bir Web Uygulamasına Dönüştürme:** Sadece bir tarayıcı uzantısı olmaktan çıkıp, kullanıcıların tüm Amazon işlerini yönetebilecekleri kapsamlı bir web uygulaması (SaaS) haline getirme.

Bu README, projenin mevcut durumunu ve potansiyelini yansıtmaktadır. Kod tabanını daha da keşfederek ve yukarıdaki fikirleri geliştirerek, FastChecker'ı Amazon satıcıları için vazgeçilmez bir araç haline getirebilirsiniz.
