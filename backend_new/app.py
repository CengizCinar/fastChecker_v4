import os
import json
import logging
import traceback
from datetime import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS
from sp_api.api import CatalogItems, ListingsRestrictions, Products, ProductFees
from sp_api.base import Marketplaces, SellingApiException

# Fix the import - use relative import since bsr_scraper.py is in the same directory
try:
    from .bsr_scraper import scrape_bsr_table_by_country
except ImportError:
    # Fallback for direct execution
    from bsr_scraper import scrape_bsr_table_by_country

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log') if os.path.exists('.') else logging.NullHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- Flask App Initialization ---
app = Flask(__name__)
CORS(app)

# --- Load BSR Data with Logging ---
logger.info("=== APPLICATION STARTUP ===")
logger.info("Loading BSR tables from SellerAmp...")
try:
    BSR_TABLES = {
        'US': scrape_bsr_table_by_country(1),
        'CA': scrape_bsr_table_by_country(6),
    }
    logger.info(f"BSR tables loaded successfully. US entries: {len(BSR_TABLES.get('US', {}))}, CA entries: {len(BSR_TABLES.get('CA', {}))}")
except Exception as e:
    logger.error(f"Error loading BSR tables: {str(e)}")
    logger.error(traceback.format_exc())
    BSR_TABLES = {'US': {}, 'CA': {}}

# --- Load Credentials from Environment Variables ---
logger.info("Loading credentials from environment variables...")
try:
    # North America (default) credentials
    credentials_na = {
        "refresh_token": os.environ['AMAZON_REFRESH_TOKEN'],
        "lwa_app_id": os.environ['AMAZON_LWA_APP_ID'],
        "lwa_client_secret": os.environ['AMAZON_LWA_CLIENT_SECRET'],
        "aws_access_key": os.environ['AWS_ACCESS_KEY_ID'],
        "aws_secret_key": os.environ['AWS_SECRET_ACCESS_KEY']
    }
    seller_id_na = os.environ['AMAZON_SELLER_ID']

    # European Union credentials
    credentials_eu = {
        "refresh_token": os.environ['EU_REFRESH_TOKEN'],
        "lwa_app_id": os.environ['EU_LWA_APP_ID'],
        "lwa_client_secret": os.environ['EU_LWA_CLIENT_SECRET'],
        "aws_access_key": os.environ['AWS_ACCESS_KEY_ID'],
        "aws_secret_key": os.environ['AWS_SECRET_ACCESS_KEY']
    }
    seller_id_eu = os.environ['EU_SELLER_ID']
    logger.info("✅ All NA and EU credentials loaded successfully")

except KeyError as e:
    logger.error(f"❌ FATAL ERROR: Environment variable not found - {e}")
    credentials_na = None
    seller_id_na = None
    credentials_eu = None
    seller_id_eu = None

# --- YENİ: Birim Dönüşüm Fonksiyonları ---
# Kodu daha temiz ve güvenilir hale getirmek için
def convert_to_cm(dimension_data):
    """Boyut objesini alır, birimi kontrol eder ve cm cinsinden float döndürür."""
    if not dimension_data or 'value' not in dimension_data or 'unit' not in dimension_data:
        return None
    try:
        value = float(dimension_data['value'])
        unit = dimension_data['unit'].lower()
        if unit in ['inches', 'inch']:
            return value * 2.54
        return value  # Zaten cm veya bilinmeyen birimse, olduğu gibi döndür
    except (ValueError, TypeError):
        return None

def convert_to_gr(weight_data):
    """Ağırlık objesini alır, birimi kontrol eder ve gram cinsinden float döndürür."""
    if not weight_data or 'value' not in weight_data or 'unit' not in weight_data:
        return None
    try:
        value = float(weight_data['value'])
        unit = weight_data['unit'].lower()
        if unit in ['pounds', 'pound', 'lb']:
            return value * 453.592
        if unit in ['kilograms', 'kilogram', 'kg']:
            return value * 1000
        if unit in ['ounces', 'ounce', 'oz']:
            return value * 28.3495
        return value # Zaten gram veya bilinmeyen birimse, olduğu gibi döndür
    except (ValueError, TypeError):
        return None

# --- Main Function to Get Product Details ---
def get_full_product_details_as_json(asin: str, marketplace_str: str):
    logger.info(f"=== PRODUCT DETAILS REQUEST ===")
    logger.info(f"ASIN: {asin}, Marketplace: {marketplace_str}")

    try:
        marketplace = getattr(Marketplaces, marketplace_str.upper())
        logger.info(f"✅ Marketplace resolved: {marketplace.marketplace_id}")
    except AttributeError:
        error_msg = f"Invalid marketplace: '{marketplace_str}'"
        logger.error(error_msg)
        return {"error": error_msg}

    # Select credentials based on marketplace region
    if marketplace.region == 'EU':
        credentials = credentials_eu
        seller_id = seller_id_eu
        logger.info("Using EU credentials")
    else:
        credentials = credentials_na
        seller_id = seller_id_na
        logger.info("Using NA credentials")

    if not credentials or not seller_id:
        error_msg = "Server is not configured for the requested region. Missing credentials or Seller ID."
        logger.error(error_msg)
        return {"error": error_msg}

    try:
        logger.info("Initializing Amazon SP APIs...")
        catalog_api = CatalogItems(credentials=credentials, marketplace=marketplace)
        restrictions_api = ListingsRestrictions(credentials=credentials, marketplace=marketplace)
        products_api = Products(credentials=credentials, marketplace=marketplace)
        fees_api = ProductFees(credentials=credentials, marketplace=marketplace)
        logger.info("✅ All APIs initialized successfully")

        result_data = {}

        # 1. Catalog Info (Attributes) - DOKUNULMADI
        logger.info("🔍 Step 1: Fetching catalog attributes...")
        try:
            catalog_response_attributes = catalog_api.get_catalog_item(asin, includedData=['summaries', 'identifiers', 'attributes'])
            logger.info("✅ Catalog attributes fetched successfully")
            
            summary = catalog_response_attributes.payload.get('summaries', [{}])[0]
            result_data['asin'] = asin
            result_data['title'] = summary.get('itemName', 'N/A')
            result_data['brand'] = summary.get('brandName', 'N/A')
            result_data['ean'] = next((i['identifier'] for i in catalog_response_attributes.payload.get('identifiers', [{}])[0].get('identifiers', []) if i.get('identifierType') == 'EAN'), 'N/A')
            
            logger.info(f"Product: {result_data['title'][:50]}...")
            logger.info(f"Brand: {result_data['brand']}")
            
        except Exception as e:
            logger.error(f"❌ Error in catalog attributes: {str(e)}")
            logger.error(traceback.format_exc())
            raise

        # 2. Image Info - DOKUNULMADI
        logger.info("🖼️ Step 2: Fetching product images...")
        try:
            catalog_response_images = catalog_api.get_catalog_item(asin, includedData=['images'])
            result_data['imageUrl'] = catalog_response_images.payload.get('images', [{}])[0].get('images', [{}])[0].get('link')
            logger.info(f"✅ Image URL: {result_data['imageUrl'][:50] if result_data['imageUrl'] else 'None'}...")
        except Exception as e:
            logger.warning(f"⚠️ Could not fetch images: {str(e)}")
            result_data['imageUrl'] = None

        # --- DÜZELTİLEN BÖLÜM BURASI ---
        # 3. Dimensions and Weight
        logger.info("📏 Step 3: Processing dimensions and weight...")
        try:
            attributes_data = catalog_response_attributes.payload.get('attributes', {})
            
            # Dimensions
            package_dims_data = attributes_data.get('item_package_dimensions', [{}])[0]
            length_cm = convert_to_cm(package_dims_data.get('length'))
            width_cm = convert_to_cm(package_dims_data.get('width'))
            height_cm = convert_to_cm(package_dims_data.get('height'))

            if all([length_cm, width_cm, height_cm]):
                result_data['dimensions'] = f"{length_cm:.2f} x {width_cm:.2f} x {height_cm:.2f} cm"
                logger.info(f"✅ Dimensions processed: {result_data['dimensions']}")
            else:
                result_data['dimensions'] = "N/A"
                logger.info("ℹ️ No complete dimensions available")

            # Weight
            package_weight_data = attributes_data.get('item_package_weight', [{}])[0]
            weight_gr = convert_to_gr(package_weight_data)
            
            if weight_gr:
                result_data['packageWeight'] = f"{weight_gr:.0f} gr"
                logger.info(f"✅ Weight processed: {result_data['packageWeight']}")
            else:
                result_data['packageWeight'] = "N/A"
                logger.info("ℹ️ No weight available")
            
            # Frontend'in hesaplama yapabilmesi için yapısal veri de ekleyelim
            result_data['package_dimensions'] = {
                "length": {"value": length_cm, "unit": "cm"},
                "width": {"value": width_cm, "unit": "cm"},
                "height": {"value": height_cm, "unit": "cm"}
            }
            result_data['package_weight'] = {
                "value": weight_gr,
                "unit": "grams"
            }

        except Exception as e:
            logger.error(f"❌ Error processing dimensions/weight: {str(e)}")
            result_data['dimensions'] = "N/A"
            result_data['packageWeight'] = "N/A"
            result_data['package_dimensions'] = None
            result_data['package_weight'] = None
        # --- DÜZELTME SONU ---

        # 4. Restrictions - DOKUNULMADI
        logger.info("🚫 Step 4: Checking selling restrictions...")
        try:
            restrictions_response = restrictions_api.get_listings_restrictions(asin=asin, sellerId=SELLER_ID, conditionType='new_new')
            restrictions = restrictions_response.payload.get('restrictions', [])
            result_data['isSellable'] = not bool(restrictions)
            result_data['restrictionReasons'] = [reason.get('message') for r in restrictions for reason in r.get('reasons', [])]
            logger.info(f"✅ Sellable: {result_data['isSellable']}, Restrictions: {len(restrictions)}")
        except Exception as e:
            logger.error(f"❌ Error checking restrictions: {str(e)}")
            logger.error(traceback.format_exc())
            result_data['isSellable'] = None
            result_data['restrictionReasons'] = []

        # 5. Offers - DOKUNULMADI
        logger.info("💰 Step 5: Fetching offers and pricing...")
        try:
            offers_response = products_api.get_item_offers(asin, "New", MarketplaceId=marketplace.marketplace_id)
            offers = offers_response.payload.get('Offers', [])
            filtered_offers = [o for o in offers if o.get('Quantity', 1) > 0 and o.get('IsFeatured', True)]
            result_data['offers'] = filtered_offers
            
            buybox_offer = next((o for o in filtered_offers if o.get('IsBuyBoxWinner')), None)
            buybox_price = float(buybox_offer['ListingPrice']['Amount']) if buybox_offer else None
            currency_code = buybox_offer['ListingPrice']['CurrencyCode'] if buybox_offer else None
            result_data['buyboxPrice'] = buybox_price
            result_data['currencyCode'] = currency_code
            
            logger.info(f"✅ Offers: {len(offers)}, Filtered: {len(filtered_offers)}")
            logger.info(f"✅ Buybox Price: {buybox_price} {currency_code}")
            
        except Exception as e:
            logger.error(f"❌ Error fetching offers: {str(e)}")
            logger.error(traceback.format_exc())
            result_data['offers'] = []
            result_data['buyboxPrice'] = None
            result_data['currencyCode'] = None
            buybox_price = None
            currency_code = None

        # 6. Fees - DOKUNULMADI
        logger.info("🧮 Step 6: Calculating fees...")
        if buybox_price:
            try:
                fees_response = fees_api.get_product_fees_estimate([{'id_type': 'ASIN', 'id_value': asin, 'price': buybox_price, 'currency': currency_code, 'is_fba': True, 'marketplace_id': marketplace.marketplace_id}])
                fees_result = fees_response.payload[0]
                
                if fees_result.get('Status') == 'Success':
                    fees_estimate = fees_result.get('FeesEstimate', {})
                    total_fees = fees_estimate.get('TotalFeesEstimate', {}).get('Amount', 0.0)
                    fee_details = fees_estimate.get('FeeDetailList', [])
                    result_data['totalFees'] = total_fees
                    result_data['referralFee'] = next((f.get('FeeAmount', {}).get('Amount', 0.0) for f in fee_details if f.get('FeeType') == "ReferralFee"), 0.0)
                    result_data['fbaFee'] = next((f.get('FeeAmount', {}).get('Amount', 0.0) for f in fee_details if f.get('FeeType') == "FBAFees"), 0.0)
                    result_data['netProfit'] = buybox_price - total_fees
                    logger.info(f"✅ Total Fees: {total_fees}, Net Profit: {result_data['netProfit']}")
                else:
                    logger.warning(f"⚠️ Fees calculation failed: {fees_result.get('Status')}")
                    result_data.update({'totalFees': None, 'referralFee': None, 'fbaFee': None, 'netProfit': None})
            except Exception as e:
                logger.error(f"❌ Error calculating fees: {str(e)}")
                logger.error(traceback.format_exc())
                result_data.update({'totalFees': None, 'referralFee': None, 'fbaFee': None, 'netProfit': None})
        else:
            logger.info("ℹ️ No buybox price available, skipping fees calculation")
            result_data.update({'totalFees': None, 'referralFee': None, 'fbaFee': None, 'netProfit': None})

        logger.info("✅ Product details fetched successfully")
        return result_data

    except SellingApiException as e:
        error_message = str(e.payload if hasattr(e, 'payload') and e.payload else e)
        logger.error(f"❌ Amazon SP API Error: {error_message}")
        logger.error(f"Full exception: {e}")
        return {"error": f"API Error: {error_message}"}

# --- API Endpoints - DOKUNULMADI ---
@app.route('/')
def health_check():
    logger.info("Health check requested")
    return jsonify({
        "status": "OK", 
        "message": "FastChecker Backend is running!",
        "timestamp": datetime.now().isoformat(),
        "credentials_loaded": bool(credentials),
        "bsr_tables_loaded": bool(BSR_TABLES.get('US')) and bool(BSR_TABLES.get('CA'))
    })

@app.route('/get_product_details/<string:asin>', methods=['GET'])
def api_get_product_details(asin):
    logger.info(f"API request received for ASIN: {asin}")
    
    if not credentials:
        logger.error("Server not configured - missing credentials")
        return jsonify({"error": "Server is not configured correctly. Please check logs."}), 503

    marketplace = request.args.get('marketplace', 'US')
    logger.info(f"Marketplace: {marketplace}")
    
    try:
        data = get_full_product_details_as_json(asin, marketplace)
        
        if "error" in data:
            logger.error(f"API returning error: {data['error']}")
            return jsonify(data), 500
        
        data['bsr_data'] = BSR_TABLES.get(marketplace.upper())
        logger.info(f"✅ API request completed successfully for ASIN: {asin}")
        return jsonify(data)
        
    except Exception as e:
        logger.error(f"❌ Unexpected error in API endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"error": f"Server error: {str(e)}"}), 500

# --- Error Handlers - DOKUNULMADI ---
@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Unhandled exception: {str(e)}")
    logger.error(traceback.format_exc())
    return jsonify({"error": "Internal server error"}), 500

# --- Server Start - DOKUNULMADI ---
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5003))
    logger.info(f"Starting Flask server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)