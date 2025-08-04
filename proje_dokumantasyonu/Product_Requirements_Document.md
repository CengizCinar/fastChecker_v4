# Ürün Gereksinimleri Dokümanı: FastChecker

**Sürüm:** 2.0
**Tarih:** 5 Ağustos 2025
**Yazar:** Gemini (AI Product Manager)

---

## 1. Vizyon ve Amaç

**Vizyonumuz:** Amazon'daki her satıcının, karmaşık veri analizini saniyeler içinde yaparak, kârlı ve doğru envanter kararları almasını sağlayan vazgeçilmez bir araç olmak.

**Projenin Amacı:** FastChecker, Amazon satıcılarının ürün araştırma ve satılabilirlik analiz süreçlerini otomatize eden bir Chrome uzantısıdır. Temel amaç, manuel ve zaman alıcı veri toplama işlemlerini ortadan kaldırarak, satıcılara anlık, eyleme geçirilebilir ve zenginleştirilmiş veriler sunmak, böylece kârlılıklarını ve operasyonel verimliliklerini en üst düzeye çıkarmaktır.

## 2. Hedef Kitle

- **Arbitraj Satıcıları (Online/Retail):** Farklı pazar yerleri veya tedarikçiler arasındaki fiyat farklarından yararlanarak ürün alıp satan, hızlı karar vermesi gereken satıcılar.
- **Wholesale (Toptan) Satıcıları:** Markalardan veya distribütörlerden toplu ürün alıp satan ve bu ürünlerin kendi hesaplarında satılıp satılamayacağını hızlıca teyit etmesi gereken satıcılar.
- **Private Label (Özel Marka) Satıcıları:** Pazar ve rakip analizi yaparak yeni ürün fırsatları arayan girişimciler.

## 3. Kullanıcı Problemleri ve Çözümler

| Kullanıcı Problemi (The "Why") | Çözümümüz (The "What") |
| :--- | :--- |
| **"Bir ürünün hesabımda satılıp satılamayacağını öğrenmek çok uzun sürüyor."** | **Toplu ASIN Kontrolü:** Yan panel üzerinden yüzlerce ASIN'in satılabilirlik durumunu saniyeler içinde kontrol etme imkanı. |
| **"Bir ürünün kârlı olup olmadığını anlamak için onlarca farklı veri kaynağını (Keepa, Seller Central, vb.) kontrol etmem gerekiyor."** | **Hepsi Bir Arada Ürün Analiz Paneli:** Ürün sayfasında, BSR, potansiyel kâr, FBA ücretleri, rakip satıcılar ve Avrupa fiyatları gibi tüm kritik verileri tek bir arayüzde sunma. |
| **"Kargo maliyetlerini hesaba katarak birim maliyeti doğru hesaplamak karmaşık."** | **Entegre Kargo Hesaplayıcı:** Kullanıcının kendi koli ve kargo ücreti ayarlarına göre birim başına düşen maliyeti otomatik hesaplama ve kâr analizine dahil etme. |
| **"Bir ürünün Avrupa'daki satış potansiyelini ve fiyatlarını görmek için tüm pazar yerlerini tek tek gezmem gerekiyor."** | **Avrupa Fiyat Karşılaştırması:** Ziyaret edilen ürünün diğer büyük Avrupa pazar yerlerindeki (DE, FR, IT, ES) B2B fiyatlarını ve Minimum Sipariş Miktarlarını (MOQ) anında gösterme. |
| **"Bir ürünün satış sıralaması (BSR) tek başına bir anlam ifade etmiyor. Kategorisindeki yerini anlamak zor."** | **Zenginleştirilmiş BSR Analizi:** BSR değerini, ait olduğu kategorideki yüzdelik dilimle ("Top 1%", "Top 5%" gibi) birlikte sunarak, satış potansiyeli hakkında daha net bir fikir verme. |

## 4. Temel Özellikler (Epics & User Stories)

### Epic 1: Yan Panel ile Hızlı Satılabilirlik Kontrolü
- **User Story 1.1:** Bir satıcı olarak, SP-API kimlik bilgilerimi uzantıya güvenli bir şekilde kaydedebilmeliyim ki API'ye erişim sağlayabileyim.
- **User Story 1.2:** Bir satıcı olarak, birden fazla ASIN'i bir metin alanına yapıştırıp "Kontrol Et" butonuna basarak bu ürünlerin seçtiğim pazar yerinde satılabilir olup olmadığını görebilmeliyim.
- **User Story 1.3:** Bir satıcı olarak, kontrol sonuçlarını (`SATILABİLİR`, `ONAY GEREKLİ`, `HATA` vb.) gerçek zamanlı olarak bir listede görebilmeliyim.
- **User Story 1.4:** Bir satıcı olarak, durumu belirsiz olan (`ONAY GEREKLİ`) ürünler için arka planda manuel bir kontrolün başlatıldığını ve sonuç geldiğinde listenin güncellendiğini görebilmeliyim.
- **User Story 1.5:** Bir satıcı olarak, tüm kontrol sonuçlarını orijinal giriş sırasına göre bir CSV dosyası olarak indirebilmeliyim.

### Epic 2: Ürün Sayfasında Derinlemesine Analiz
- **User Story 2.1:** Bir satıcı olarak, bir Amazon ürün sayfasını ziyaret ettiğimde, sayfanın içinde FastChecker tarafından eklenmiş bir analiz paneli görebilmeliyim.
- **User Story 2.2:** Panelde, ürünün temel bilgilerini (ASIN, EAN, marka, boyut, ağırlık) ve satılabilirlik durumunu net bir şekilde görebilmeliyim.
- **User Story 2.3:** Panelde, ürünün Buy Box fiyatını ve Amazon ücretlerini (Referral, FBA) kullanarak ve kendi maliyetimi girerek potansiyel kâr, ROI ve başa baş satış fiyatını anında hesaplayabilmeliyim.
- **User Story 2.4:** Panelde, ürünü satan diğer FBA ve FBM satıcılarını ve fiyatlarını liste halinde görebilmeliyim.
- **User Story 2.5:** Panelde, ürünün diğer Avrupa pazar yerlerindeki fiyatlarını ve varsa minimum sipariş miktarlarını görebilmeliyim.
- **User Story 2.6:** Panelde, ürünün BSR değerini ve bu değerin kategorisindeki önemini ("Top 1%") belirten bir analiz görebilmeliyim.

## 5. Başarı Metrikleri

- **Aktivasyon Oranı:** Uzantıyı yükleyen kullanıcıların %70'inin ilk 24 saat içinde en az bir ASIN kontrolü yapması veya bir ürün sayfasını analiz etmesi.
- **Haftalık Aktif Kullanıcı (WAU):** Haftalık aktif kullanıcı sayısının ayda %10 artması.
- **Görev Tamamlama Oranı:** Başlatılan toplu ASIN kontrollerinin %95'inin başarıyla (hata olmadan) tamamlanması.
- **Kullanıcı Memnuniyeti (NPS):** Kullanıcılardan alınacak geri bildirimlerle Net Promoter Score'un +40 üzerinde olması.

## 6. Kapsam Dışı (Gelecek Sürümler İçin)

- Tarihsel veri takibi (Fiyat, BSR geçmişi).
- Otomatik fiyatlandırma önerileri.
- Envanter yönetimi entegrasyonu.
- Diğer e-ticaret platformları için destek (eBay, Walmart vb.).
