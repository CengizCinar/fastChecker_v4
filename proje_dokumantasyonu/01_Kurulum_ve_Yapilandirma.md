# FastChecker: Kurulum ve Kullanım Kılavuzu

**Sürüm:** 2.0
**Tarih:** 5 Ağustos 2025

---

Bu kılavuz, FastChecker uzantısını nasıl kuracağınızı ve tüm özelliklerinden nasıl faydalanacağınızı adım adım açıklar.

## Bölüm 1: Son Kullanıcılar İçin Hızlı Başlangıç

Bu bölüm, sadece uzantıyı kullanmak isteyen satıcılar içindir.

### 1.1. Uzantıyı Chrome'a Yükleme

1.  **Google Chrome:** Bilgisayarınızda güncel bir Google Chrome tarayıcısı kurulu olmalıdır.
2.  **Uzantı Sayfasını Açın:** Chrome'u açın ve adres çubuğuna `chrome://extensions` yazıp Enter'a basın.
3.  **Geliştirici Modunu Aktif Edin:** Sayfanın sağ üst köşesindeki **"Geliştirici modu"** (Developer mode) anahtarını açık konuma getirin.
4.  **Uzantıyı Yükleyin:**
    *   Sol üstte beliren **"Paketlenmemiş öğe yükle"** (Load unpacked) butonuna tıklayın.
    *   Açılan pencerede, size verilen FastChecker proje klasörünü (`.../FastChecker_v4 copy/`) seçin ve "Aç" veya "Seç" butonuna tıklayın.

    ![Kurulum Adımları](https://i.imgur.com/your_installation_guide_image.png) <!-- Varsayımsal resim linki -->

5.  **Kurulum Tamamlandı!** FastChecker ikonu, tarayıcınızın sağ üst köşesindeki uzantılar çubuğuna eklenecektir.

### 1.2. İlk Kurulum: SP-API Ayarları

Uzantının çalışabilmesi için Amazon Satıcı Hesabınıza bağlanması gerekir.

1.  **Yan Paneli Açın:** Herhangi bir web sayfasındayken, tarayıcınızın sağ kenarındaki **Yan Panel** ikonuna ve ardından menüden **newChecker**'ı seçin.
2.  **Ayarları Girin:** Yan panelde açılan **"SP-API Ayarları"** bölümüne, size Amazon tarafından sağlanan aşağıdaki bilgileri eksiksiz girin:
    -   **Refresh Token**
    -   **Client ID**
    -   **Client Secret**
    -   **Satıcı ID (Seller ID)**
    -   **Pazaryeri (Marketplace):** İşlem yapmak istediğiniz ana pazar yerini seçin (örn: US, DE, CA).
3.  **Kaydedin:** **"Ayarları Kaydet"** butonuna tıklayın. Başarılı bir şekilde kaydedildiğine dair bir bildirim göreceksiniz.

### 1.3. Özellikleri Kullanma

#### a) Toplu ASIN Kontrolü (Yan Panel)

1.  **ASIN'leri Girin:** "ASIN Kontrol" bölümündeki metin alanına, kontrol etmek istediğiniz ASIN'leri aralarına virgül veya boşluk koyarak yapıştırın.
2.  **Kontrolü Başlatın:** **"Kontrol Et"** butonuna tıklayın.
3.  **Sonuçları İzleyin:** Sonuçlar, alt taraftaki sonuçlar listesine gerçek zamanlı olarak düşmeye başlayacaktır. Durumu belirsiz olan ürünler için manuel kontrol otomatik olarak başlar ve sonuçlandığında liste güncellenir.
4.  **Sonuçları İndirin:** Tüm kontroller bittiğinde, **"Sonuçları CSV Olarak İndir"** butonu belirir. Bu butona tıklayarak tüm listeyi bilgisayarınıza indirebilirsiniz.

#### b) Ürün Sayfasında Analiz

1.  **Amazon Ürün Sayfasına Gidin:** Herhangi bir Amazon ürün detay sayfasını (`.../dp/ASIN`) ziyaret edin.
2.  **Paneli Gözlemleyin:** Sayfanın sağ tarafında, FastChecker analiz paneli otomatik olarak belirecektir.
3.  **Analizi İnceleyin:** Panelde ürünün satılabilirlik durumu, kâr hesaplayıcısı, BSR analizi, rakip satıcılar ve Avrupa fiyatları gibi birçok kritik bilgiyi anında görebilirsiniz.
4.  **Kâr Hesaplayın:** "Profit Calculator" bölümündeki **"Cost"** alanına ürünün size olan maliyetini girerek net kâr, ROI ve başa baş satış fiyatını anlık olarak hesaplayabilirsiniz.

---

## Bölüm 2: Geliştiriciler İçin Kurulum

Bu bölüm, proje kodunu incelemek, değiştirmek veya geliştirmek isteyen yazılımcılar içindir.

### 2.1. Ön Gereksinimler

-   **Google Chrome**
-   **Python 3.8+** ve `pip`
-   **Git** (versiyon kontrolü için)

### 2.2. Projeyi Kurma

1.  **Projeyi Klonlayın:**
    ```bash
    git clone <projenin_git_adresi>
    cd FastChecker_v4
    ```

2.  **Uzantıyı Yükleyin:** Yukarıdaki "Son Kullanıcılar İçin" bölümündeki **Adım 1.1**'i takip ederek uzantıyı Chrome'a yükleyin.

3.  **Backend'i Kurun ve Çalıştırın:**
    -   Backend klasörüne gidin:
        ```bash
        cd backend_new
        ```
    -   Gerekli Python kütüphanelerini yükleyin:
        ```bash
        pip install -r requirements.txt
        ```
    -   **ÖNEMLİ:** Backend'in çalışması için gerekli olan SP-API ve AWS kimlik bilgilerini ortam değişkenleri (environment variables) olarak ayarlamanız gerekir. Proje ana dizinindeki `.env.example` dosyasını kopyalayıp `.env` olarak adlandırın ve içini kendi bilgilerinizle doldurun. Geliştirme ortamında bu değişkenlerin yüklenmesi için `python-dotenv` kütüphanesi kullanılabilir.
    -   Sunucuyu başlatın:
        ```bash
        python app.py
        ```
    -   Sunucu varsayılan olarak `http://127.0.0.1:5003` adresinde çalışmaya başlayacaktır.

### 2.3. Geliştirme İpuçları

-   **Uzantıyı Yeniden Yükleme:** Uzantı kodunda (`.js`, `.css`, `.html`) bir değişiklik yaptığınızda, `chrome://extensions` sayfasına gidip FastChecker kartındaki **yenileme ikonuna** tıklayarak uzantıyı yeniden yüklemeniz gerekir.
-   **Hata Ayıklama (Debugging):**
    -   **`background.js`:** `chrome://extensions` sayfasındaki FastChecker kartında bulunan **"Service Worker'ı incele"** linkine tıklayarak konsol kayıtlarını görebilirsiniz.
    -   **`content.js`:** Normal bir web sayfası gibi, Amazon ürün sayfasındayken `Sağ Tık > İncele` ile açılan Geliştirici Araçları'nın **Console** sekmesinden takip edilebilir.
    -   **`sidepanel.js`:** Yan panel açıkken, panele sağ tıklayıp **"İncele"** seçeneğini seçerek kendi Geliştirici Araçları penceresini açabilirsiniz.
-   **Kod Yapısı:** Projeyi değiştirmeden önce `proje_dokumantasyonu/Technical_Design_Document.md` dosyasını okuyarak mimariyi ve bileşenlerin sorumluluklarını anladığınızdan emin olun.