import os
import json
import logging
import traceback
from datetime import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS
from sp_api.api import CatalogItems, ListingsRestrictions, Products, ProductFees
from sp_api.base import Marketplaces, SellingApiException
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
    credentials = {
        "refresh_token": os.environ['AMAZON_REFRESH_TOKEN'],
        "lwa_app_id": os.environ['AMAZON_LWA_APP_ID'],
        "lwa_client_secret": os.environ['AMAZON_LWA_CLIENT_SECRET'],
        "aws_access_key": os.environ['AWS_ACCESS_KEY_ID'],
        "aws_secret_key": os.environ['AWS_SECRET_ACCESS_KEY']
    }
    SELLER_ID = os.environ['AMAZON_SELLER_ID']
    logger.info("✅ All credentials loaded successfully")
    logger.info(f"Seller ID: {SELLER_ID[:10]}...")  # Only show first 10 chars for security
    logger.info(f"LWA App ID: {credentials['lwa_app_id'][:10]}...")
except KeyError as e:
    logger.error(f"❌ FATAL ERROR: Environment variable not found - {e}")
    logger.error("Required environment variables:")
    logger.error("- AMAZON_REFRESH_TOKEN")
    logger.error("- AMAZON_LWA_APP_ID") 
    logger.error("- AMAZON_LWA_CLIENT_SECRET")
    logger.error("- AWS_ACCESS_KEY_ID")
    logger.error("- AWS_SECRET_ACCESS_KEY")
    logger.error("- AMAZON_SELLER_ID")
    credentials = None
    SELLER_ID = None

# --- Main Function to Get Product Details ---
def get_full_product_details_as_json(asin: str, marketplace_str: str):
    logger.info(f"=== PRODUCT DETAILS REQUEST ===")
    logger.info(f"ASIN: {asin}, Marketplace: {marketplace_str}")
    
    if not credentials or not SELLER_ID:
        error_msg = "Server is not configured. Missing credentials or Seller ID."
        logger.error(error_msg)
        return {"error": error_msg}

    try:
        marketplace = getattr(Marketplaces, marketplace_str.upper())
        logger.info(f"✅ Marketplace resolved: {marketplace.marketplace_id}")
    except AttributeError:
        error_msg = f"Invalid marketplace: '{marketplace_str}'"
        logger.error(error_msg)
        return {"error": error_msg}

    try:
        logger.info("Initializing Amazon SP APIs...")
        # Initialize APIs with the credentials loaded from environment variables
        catalog_api = CatalogItems(credentials=credentials, marketplace=marketplace)
        restrictions_api = ListingsRestrictions(credentials=credentials, marketplace=marketplace)
        products_api = Products(credentials=credentials, marketplace=marketplace)
        fees_api = ProductFees(credentials=credentials, marketplace=marketplace)
        logger.info("✅ All APIs initialized successfully")

        result_data = {}

        # 1. Catalog Info (Attributes)
        logger.info("🔍 Step 1: Fetching catalog attributes...")
        try:
            catalog_response_attributes = catalog_api.get_catalog_item(asin, includedData=['summaries', 'identifiers', 'attributes'])
            logger.info("✅ Catalog attributes fetched successfully")
            
            summary = catalog_response_attributes.payload.get('summaries', [{}])[0]
            result_data['asin'] = asin
            result_data['title'] = summary.get('itemName', 'N/A')
            result_data['brand'] = summary.get('brandName', 'N/A')
            result_data['ean'] = next((i['identifier'] for i in catalog_response_attributes.payload.get('identifiers', [{}])[0].get('identifiers', []) if i['identifierType'] == 'EAN'), 'N/A')
            
            logger.info(f"Product: {result_data['title'][:50]}...")
            logger.info(f"Brand: {result_data['brand']}")
            
        except Exception as e:
            logger.error(f"❌ Error in catalog attributes: {str(e)}")
            logger.error(traceback.format_exc())
            raise

        # 2. Image Info
        logger.info("🖼️ Step 2: Fetching product images...")
        try:
            catalog_response_images = catalog_api.get_catalog_item(asin, includedData=['images'])
            result_data['imageUrl'] = catalog_response_images.payload.get('images', [{}])[0].get('images', [{}])[0].get('link')
            logger.info(f"✅ Image URL: {result_data['imageUrl'][:50] if result_data['imageUrl'] else 'None'}...")
        except Exception as e:
            logger.warning(f"⚠️ Could not fetch images: {str(e)}")
            result_data['imageUrl'] = None

        # 3. Dimensions and Weight
        logger.info("📏 Step 3: Processing dimensions and weight...")
        try:
            attributes_data = catalog_response_attributes.payload.get('attributes', {})
            
            # Dimensions
            package_dims = attributes_data.get('item_package_dimensions', [{}])[0]
            if package_dims and 'value' in package_dims.get('length', {}):
                length = package_dims['length']['value'] * 2.54
                width = package_dims['width']['value'] * 2.54
                height = package_dims['height']['value'] * 2.54
                result_data['dimensions'] = f"{length:.1f} x {width:.1f} x {height:.1f} cm"
                logger.info(f"✅ Dimensions: {result_data['dimensions']}")
            else:
                result_data['dimensions'] = "N/A"
                logger.info("ℹ️ No dimensions available")

            # Weight
            package_weight = attributes_data.get('item_package_weight', [{}])[0]
            if package_weight and 'value' in package_weight:
                weight_value = package_weight['value']
                weight_unit = package_weight.get('unit', '')
                if weight_unit.lower() in ['pounds', 'pound']:
                    weight_kg = weight_value * 0.453592
                    result_data['packageWeight'] = f"{(weight_kg * 1000):.0f} gr"
                else:
                    try:
                        result_data['packageWeight'] = f"{float(weight_value) * 1000:.0f} gr"
                    except (ValueError, TypeError):
                        result_data['packageWeight'] = "N/A"
                logger.info(f"✅ Weight: {result_data['packageWeight']}")
            else:
                result_data['packageWeight'] = "N/A"
                logger.info("ℹ️ No weight available")
                
        except Exception as e:
            logger.error(f"❌ Error processing dimensions/weight: {str(e)}")
            result_data['dimensions'] = "N/A"
            result_data['packageWeight'] = "N/A"

        # 4. Restrictions
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

        # 5. Offers
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

        # 6. Fees
        logger.info("🧮 Step 6: Calculating fees...")
        if buybox_price:
            try:
                fees_response = fees_api.get_product_fees_estimate([{
                    'id_type': 'ASIN', 
                    'id_value': asin, 
                    'price': buybox_price, 
                    'currency': currency_code, 
                    'is_fba': True, 
                    'marketplace_id': marketplace.marketplace_id
                }])
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
        error_message = str(e.payload or e)
        logger.error(f"❌ Amazon SP API Error: {error_message}")
        logger.error(f"Full exception: {e}")
        return {"error": f"API Error: {error_message}"}
    except Exception as e:
        logger.error(f"❌ Unexpected error: {str(e)}")
        logger.error(traceback.format_exc())
        return {"error": f"An unexpected server error occurred: {str(e)}"}

# --- API Endpoints ---
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

# --- Error Handlers ---
@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Unhandled exception: {str(e)}")
    logger.error(traceback.format_exc())
    return jsonify({"error": "Internal server error"}), 500

# --- Server Start ---
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5003))
    logger.info(f"Starting Flask server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)