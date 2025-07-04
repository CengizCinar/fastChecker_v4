import json
import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from pathlib import Path
import sys
from typing import Dict, Any

from sp_api.api import CatalogItems, ListingsRestrictions, Products, ProductFees
from sp_api.base import Marketplaces, SellingApiException

from bsr_scraper import scrape_bsr_table_by_country

# --- Flask Uygulamasını Başlatma ---
app = Flask(__name__)
CORS(app) # Uzantıdan gelen isteklere izin vermek için

# --- BSR Verisini Yükleme ---
print("BSR tabloları SellerAmp'ten alınıyor...")
BSR_TABLES = {
    'US': scrape_bsr_table_by_country(1),
    'CA': scrape_bsr_table_by_country(6),
    # Diğer pazar yerleri eklenebilir...
}
print("BSR tabloları yüklendi.")

# --- Yapılandırma ve Credential Yükleme ---
def load_config():
    """
    Önce environment variables'dan credential'ları oku,
    yoksa config.json'dan oku
    """
    # Environment variables'dan oku (production için)
    refresh_token = os.environ.get('AMAZON_REFRESH_TOKEN')
    lwa_app_id = os.environ.get('AMAZON_LWA_APP_ID')
    lwa_client_secret = os.environ.get('AMAZON_LWA_CLIENT_SECRET')
    seller_id = os.environ.get('AMAZON_SELLER_ID')
    
    if all([refresh_token, lwa_app_id, lwa_client_secret, seller_id]):
        return {
            "credentials": {
                "refresh_token": refresh_token,
                "lwa_app_id": lwa_app_id,
                "lwa_client_secret": lwa_client_secret
            },
            "test_parameters": {
                "seller_id": seller_id,
                "marketplace": "US"
            }
        }
    
    # Environment variables yoksa config.json'dan oku (development için)
    config_path = Path(__file__).parent / "config.json"
    if not config_path.is_file():
        return {"error": "config.json bulunamadı ve environment variables da ayarlanmamış."}
    
    try:
        with config_path.open('r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {"error": "config.json geçersiz formatta."}

CONFIG = load_config()
if "error" in CONFIG:
    print(f"HATA: {CONFIG['error']}")

# --- Ana Fonksiyon ---
def get_full_product_details_as_json(asin: str, marketplace_str: str):
    creds = CONFIG.get("credentials", {})
    params = CONFIG.get("test_parameters", {})
    seller_id = params.get("seller_id")

    if not all([creds, seller_id, marketplace_str]):
        return {"error": "Credentials, seller_id eksik veya pazar yeri belirtilmedi."}

    try:
        marketplace = getattr(Marketplaces, marketplace_str.upper())
    except AttributeError:
        return {"error": f"Geçersiz pazar yeri: '{marketplace_str}'."}

    try:
        # API istemcilerini başlat
        catalog_api = CatalogItems(credentials=creds, marketplace=marketplace)
        restrictions_api = ListingsRestrictions(credentials=creds, marketplace=marketplace)
        products_api = Products(credentials=creds, marketplace=marketplace)
        fees_api = ProductFees(credentials=creds, marketplace=marketplace)

        # Tüm verileri toplamak için bir dictionary oluştur
        result_data = {}

        # 1. Katalog Bilgileri (Ağırlık ve diğer nitelikler için)
        catalog_response_attributes = catalog_api.get_catalog_item(asin, includedData=['summaries', 'identifiers', 'attributes'])
        summary = catalog_response_attributes.payload.get('summaries', [{}])[0]
        result_data['asin'] = asin
        result_data['title'] = summary.get('itemName', 'N/A')
        result_data['brand'] = summary.get('brandName', 'N/A')
        result_data['ean'] = next((i['identifier'] for i in catalog_response_attributes.payload.get('identifiers', [{}])[0].get('identifiers', []) if i['identifierType'] == 'EAN'), 'N/A')

        # 2. Resim Bilgisi (Ayrı bir API isteği ile)
        try:
            catalog_response_images = catalog_api.get_catalog_item(asin, includedData=['images'])
            result_data['imageUrl'] = catalog_response_images.payload.get('images', [{}])[0].get('images', [{}])[0].get('link')
        except SellingApiException:
            result_data['imageUrl'] = None # Resim alınamazsa hata verme, devam et

        # 3. Boyut ve Ağırlık Bilgileri (Formatlanmış)
        attributes_data = catalog_response_attributes.payload.get('attributes', {})
        
        package_dims = attributes_data.get('item_package_dimensions', [{}])[0]
        if package_dims and 'value' in package_dims.get('length', {}):
            length = package_dims.get('length', {}).get('value', 0) * 2.54
            width = package_dims.get('width', {}).get('value', 0) * 2.54
            height = package_dims.get('height', {}).get('value', 0) * 2.54
            result_data['dimensions'] = f"{length:.1f} x {width:.1f} x {height:.1f} cm"
        else:
            result_data['dimensions'] = "N/A"

        package_weight = attributes_data.get('item_package_weight', [{}])[0]
        if package_weight and 'value' in package_weight:
            weight_value = package_weight.get('value', 0)
            weight_unit = package_weight.get('unit', '')
            if weight_unit.lower() in ['pounds', 'pound']:
                weight_kg = weight_value * 0.453592
                result_data['packageWeight'] = f"{(weight_kg * 1000):.0f} gr"
            else: # Diğer birimleri de grama çevirmeye çalışalım (varsayılan kg)
                try:
                    weight_kg = float(weight_value)
                    result_data['packageWeight'] = f"{(weight_kg * 1000):.0f} gr"
                except (ValueError, TypeError):
                     result_data['packageWeight'] = "N/A"
        else:
            result_data['packageWeight'] = "N/A"
        
        # 2. Kısıtlamalar
        restrictions_response = restrictions_api.get_listings_restrictions(asin=asin, sellerId=seller_id, conditionType='new_new')
        restrictions = restrictions_response.payload.get('restrictions', [])
        result_data['isSellable'] = not bool(restrictions)
        result_data['restrictionReasons'] = [reason.get('message') for r in restrictions for reason in r.get('reasons', [])]

        # 3. Teklifler (Offers)
        offers_response = products_api.get_item_offers(asin, "New", MarketplaceId=marketplace.marketplace_id)
        offers = offers_response.payload.get('Offers', [])
        # Sadece aktif satıcıları filtrele (Quantity > 0 veya IsFeatured/IsActive varsa)
        filtered_offers = []
        for offer in offers:
            qty = offer.get('Quantity', 1) # Quantity yoksa 1 kabul et
            is_active = offer.get('IsFeatured', True) # IsFeatured yoksa aktif kabul et
            if qty and qty > 0 and is_active:
                filtered_offers.append(offer)
        result_data['offers'] = filtered_offers
        buybox_offer = next((o for o in filtered_offers if o.get('IsBuyBoxWinner')), None)
        buybox_price = float(buybox_offer['ListingPrice']['Amount']) if buybox_offer else None
        currency_code = buybox_offer['ListingPrice']['CurrencyCode'] if buybox_offer else None
        result_data['buyboxPrice'] = buybox_price
        result_data['currencyCode'] = currency_code

        # 4. Ücretler (Fees)
        total_fees, referral_fee, fba_fee, net_profit = None, None, None, None
        if buybox_price:
            fees_response = fees_api.get_product_fees_estimate([{'id_type': 'ASIN', 'id_value': asin, 'price': buybox_price, 'currency': currency_code, 'is_fba': True, 'marketplace_id': marketplace.marketplace_id}])
            fees_result = fees_response.payload[0]
            if fees_result.get('Status') == 'Success':
                fees_estimate = fees_result.get('FeesEstimate', {})
                total_fees = fees_estimate.get('TotalFeesEstimate', {}).get('Amount', 0.0)
                fee_details = fees_estimate.get('FeeDetailList', [])
                referral_fee = next((f.get('FeeAmount', {}).get('Amount', 0.0) for f in fee_details if f.get('FeeType') == "ReferralFee"), 0.0)
                fba_fee = next((f.get('FeeAmount', {}).get('Amount', 0.0) for f in fee_details if f.get('FeeType') == "FBAFees"), 0.0)
                net_profit = buybox_price - total_fees

        result_data['totalFees'] = total_fees
        result_data['referralFee'] = referral_fee
        result_data['fbaFee'] = fba_fee
        result_data['netProfit'] = net_profit

        return result_data

    except SellingApiException as e:
        # Yetki hatası gibi bazı istisnaların 'payload'u olmayabilir.
        if hasattr(e, 'payload') and e.payload:
            error_message = e.payload.get('errors', [{}])[0].get('message', str(e))
            print(f"API Hatası (payload ile): {e.payload}")
        else:
            error_message = str(e)
            print(f"API Hatası (payload olmadan): {e}")
        return {"error": f"API Hatası: {error_message}"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": f"Beklenmedik bir sunucu hatası oluştu: {str(e)}"}

# --- API ENDPOINT'İ ---
@app.route('/')
def health_check():
    return jsonify({"status": "OK", "message": "FastChecker Backend is running!"})

@app.route('/get_product_details/<string:asin>', methods=['GET'])
def api_get_product_details(asin):
    if "error" in CONFIG:
        return jsonify(CONFIG), 500
    
    # Pazar yerini URL parametresinden al, varsayılan olarak 'US' kullan
    marketplace = request.args.get('marketplace', 'US')
    
    # Tüm detayları JSON olarak al
    data = get_full_product_details_as_json(asin, marketplace)
    
    if "error" in data:
        # Hata varsa, hatayı da JSON olarak döndür
        return jsonify(data), 500
    
    # Başarılı ise, tüm veri paketini JSON olarak döndür
    data['bsr_data'] = BSR_TABLES.get(marketplace.upper())
    return jsonify(data)

# --- SUNUCUYU BAŞLATMA ---
if __name__ == '__main__':
    # Production'da port environment variable'dan alınır
    port = int(os.environ.get('PORT', 5003))
    print(f"FastChecker backend sunucusu port {port} üzerinde başlatılıyor...")
    app.run(host='0.0.0.0', port=port, debug=False)