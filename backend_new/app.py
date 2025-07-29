import os
import json
import logging
import traceback
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from sp_api.api import CatalogItems, ListingsRestrictions, Products, ProductFees
from sp_api.base import Marketplaces, SellingApiException

# Fix the import - use relative import since bsr_scraper.py is in the same directory
try:
    from .bsr_scraper import scrape_bsr_table_by_country
except ImportError:
    # Fallback for direct execution
    from bsr_scraper import scrape_bsr_table_by_country

import requests

# --- Exchange Rate Cache --- 
EXCHANGE_RATE_API_KEY = os.environ.get('EXCHANGE_RATE_API_KEY')
EXCHANGE_RATE_CACHE_FILE = 'exchange_rate_cache.json'

def get_exchange_rates():
    if not EXCHANGE_RATE_API_KEY:
        logger.warning("EXCHANGE_RATE_API_KEY is not set. Currency conversion will be disabled.")
        return None

    try:
        if os.path.exists(EXCHANGE_RATE_CACHE_FILE):
            with open(EXCHANGE_RATE_CACHE_FILE, 'r') as f:
                cache = json.load(f)
                # Check if cache is less than 24 hours old
                if datetime.now() - datetime.fromisoformat(cache['timestamp']) < timedelta(days=1):
                    logger.info("Using cached exchange rates.")
                    return cache['rates']
    except (IOError, json.JSONDecodeError) as e:
        logger.error(f"Could not read exchange rate cache: {e}")

    logger.info("Fetching new exchange rates from API...")
    try:
        response = requests.get(f"https://v6.exchangerate-api.com/v6/{EXCHANGE_RATE_API_KEY}/latest/EUR")
        response.raise_for_status()
        data = response.json()
        if data.get('result') == 'success':
            rates = data['conversion_rates']
            with open(EXCHANGE_RATE_CACHE_FILE, 'w') as f:
                json.dump({'timestamp': datetime.now().isoformat(), 'rates': rates}, f)
            logger.info("Successfully fetched and cached new exchange rates.")
            return rates
        else:
            logger.error(f"Exchange rate API error: {data.get('error-type')}")
            return None
    except requests.RequestException as e:
        logger.error(f"Failed to fetch exchange rates: {e}")
        return None

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

# --- Marketplace Configuration ---
MARKETPLACE_REGIONS = {
    # North America (NA) - Same credentials, different domains
    'US': {'region': 'NA', 'marketplace_id': 'ATVPDKIKX0DER'},
    'CA': {'region': 'NA', 'marketplace_id': 'A2EUQ1WTGCTBG2'},
    'MX': {'region': 'NA', 'marketplace_id': 'A1AM78C64UM0Y8'},
    
    # Europe (EU) - Different credentials
    'DE': {'region': 'EU', 'marketplace_id': 'A1PA6795UKMFR9'},
    'GB': {'region': 'EU', 'marketplace_id': 'A1F83G8C2ARO7P'},
    'FR': {'region': 'EU', 'marketplace_id': 'A13V1IB3VIYZZH'},
    'IT': {'region': 'EU', 'marketplace_id': 'APJ6JRA9NG5V4'},
    'ES': {'region': 'EU', 'marketplace_id': 'A1RKKUPIHCS9HS'},
    'NL': {'region': 'EU', 'marketplace_id': 'A1805IZSGTT6HS'},
    'SE': {'region': 'EU', 'marketplace_id': 'A2NODRKZP88ZB9'},
    'PL': {'region': 'EU', 'marketplace_id': 'A1C3SOZRARQ6R3'},
    'BE': {'region': 'EU', 'marketplace_id': 'AMEN7PMS3EDWL'},
}

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
    # AWS credentials are the same for both regions
    aws_access_key = os.environ['AWS_ACCESS_KEY_ID']
    aws_secret_key = os.environ['AWS_SECRET_ACCESS_KEY']
    
    # NA Region credentials (US, CA, MX)
    na_credentials = {
        "refresh_token": os.environ['AMAZON_REFRESH_TOKEN'],
        "lwa_app_id": os.environ['AMAZON_LWA_APP_ID'],
        "lwa_client_secret": os.environ['AMAZON_LWA_CLIENT_SECRET'],
        "aws_access_key": aws_access_key,
        "aws_secret_key": aws_secret_key
    }
    na_seller_id = os.environ['AMAZON_SELLER_ID']
    
    # EU Region credentials (if available) - using same AWS keys
    eu_credentials = None
    eu_seller_id = None
    
    # Check if EU SP-API credentials are available
    if all(key in os.environ for key in ['EU_REFRESH_TOKEN', 'EU_LWA_APP_ID', 'EU_LWA_CLIENT_SECRET', 'EU_SELLER_ID']):
        eu_credentials = {
            "refresh_token": os.environ['EU_REFRESH_TOKEN'],
            "lwa_app_id": os.environ['EU_LWA_APP_ID'],
            "lwa_client_secret": os.environ['EU_LWA_CLIENT_SECRET'],
            "aws_access_key": aws_access_key,  # Same AWS keys
            "aws_secret_key": aws_secret_key   # Same AWS keys
        }
        eu_seller_id = os.environ['EU_SELLER_ID']
        logger.info("✅ Both NA and EU credentials loaded successfully (shared AWS keys)")
    else:
        logger.info("✅ NA credentials loaded successfully, EU credentials not configured")
    
    logger.info(f"NA Seller ID: {na_seller_id[:10]}...")  # Only show first 10 chars for security
    logger.info(f"NA LWA App ID: {na_credentials['lwa_app_id'][:10]}...")
    if eu_seller_id:
        logger.info(f"EU Seller ID: {eu_seller_id[:10]}...")
        logger.info(f"EU LWA App ID: {eu_credentials['lwa_app_id'][:10]}...")
        
except KeyError as e:
    logger.error(f"❌ FATAL ERROR: Environment variable not found - {e}")
    logger.error("Required environment variables:")
    logger.error("- AWS_ACCESS_KEY_ID (shared for both regions)")
    logger.error("- AWS_SECRET_ACCESS_KEY (shared for both regions)")
    logger.error("- AMAZON_REFRESH_TOKEN (NA region)")
    logger.error("- AMAZON_LWA_APP_ID (NA region)")
    logger.error("- AMAZON_LWA_CLIENT_SECRET (NA region)")
    logger.error("- AMAZON_SELLER_ID (NA region)")
    logger.error("Optional environment variables for EU region:")
    logger.error("- EU_REFRESH_TOKEN")
    logger.error("- EU_LWA_APP_ID")
    logger.error("- EU_LWA_CLIENT_SECRET")
    logger.error("- EU_SELLER_ID")
    na_credentials = None
    eu_credentials = None
    na_seller_id = None
    eu_seller_id = None

def get_credentials_for_marketplace(marketplace_str):
    """Get the appropriate credentials and seller ID for the given marketplace"""
    marketplace_info = MARKETPLACE_REGIONS.get(marketplace_str.upper())
    if not marketplace_info:
        return None, None, f"Unsupported marketplace: {marketplace_str}"
    
    region = marketplace_info['region']
    
    if region == 'NA':
        if not na_credentials or not na_seller_id:
            return None, None, "NA credentials not configured"
        return na_credentials, na_seller_id, None
    elif region == 'EU':
        if not eu_credentials or not eu_seller_id:
            return None, None, "EU credentials not configured"
        return eu_credentials, eu_seller_id, None
    else:
        return None, None, f"Unknown region: {region}"

# --- Main Function to Get Product Details ---
def get_full_product_details_as_json(asin: str, marketplace_str: str):
    logger.info(f"=== PRODUCT DETAILS REQUEST ===")
    logger.info(f"ASIN: {asin}, Marketplace: {marketplace_str}")
    
    # Get credentials for the marketplace
    credentials, seller_id, error = get_credentials_for_marketplace(marketplace_str)
    if error:
        logger.error(f"❌ Credential error: {error}")
        return {"error": error}

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
                # Check if dimensions are in inches and convert to cm
                length_unit = package_dims['length'].get('unit', '').lower()
                width_unit = package_dims['width'].get('unit', '').lower()
                height_unit = package_dims['height'].get('unit', '').lower()
                
                length = package_dims['length']['value']
                width = package_dims['width']['value']
                height = package_dims['height']['value']
                
                # Convert to cm if in inches
                if length_unit in ['inches', 'inch']:
                    length *= 2.54
                if width_unit in ['inches', 'inch']:
                    width *= 2.54
                if height_unit in ['inches', 'inch']:
                    height *= 2.54
                
                result_data['dimensions'] = f"{length:.1f} x {width:.1f} x {height:.1f} cm"
                logger.info(f"✅ Dimensions: {result_data['dimensions']}")
            else:
                result_data['dimensions'] = "N/A"
                logger.info("ℹ️ No dimensions available")

            # Weight
            package_weight = attributes_data.get('item_package_weight', [{}])[0]
            if package_weight and 'value' in package_weight:
                weight_value = package_weight['value']
                weight_unit = package_weight.get('unit', '').lower()
                
                if weight_unit in ['pounds', 'pound']:
                    # Convert pounds to grams
                    weight_gr = weight_value * 453.592
                    result_data['packageWeight'] = f"{weight_gr:.0f} gr"
                elif weight_unit in ['kilograms', 'kg']:
                    # Convert kg to grams
                    weight_gr = weight_value * 1000
                    result_data['packageWeight'] = f"{weight_gr:.0f} gr"
                elif weight_unit in ['grams', 'g']:
                    # Already in grams
                    result_data['packageWeight'] = f"{weight_value:.0f} gr"
                else:
                    # Assume it's already in grams if no unit specified
                    try:
                        result_data['packageWeight'] = f"{float(weight_value):.0f} gr"
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
            restrictions_response = restrictions_api.get_listings_restrictions(asin=asin, sellerId=seller_id, conditionType='new_new')
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
        buybox_price = None
        currency_code = None
        try:
            offers_response = products_api.get_item_offers(asin, "New", MarketplaceId=marketplace.marketplace_id)
            offers = offers_response.payload.get('Offers', [])
            
            processed_offers = []
            for o in offers:
                # FBM teklifleri için kargo ücretini fiyata ekle
                if not o.get('IsFulfilledByAmazon', False):
                    listing_price = o.get('ListingPrice', {}).get('Amount', 0.0)
                    shipping_price = o.get('Shipping', {}).get('Amount', 0.0)
                    o['ListingPrice']['Amount'] = float(listing_price) + float(shipping_price)
                processed_offers.append(o)

            # Fiyatlarına göre sırala
            processed_offers.sort(key=lambda x: x.get('ListingPrice', {}).get('Amount', float('inf')))
            
            result_data['offers'] = processed_offers
            
            # Buy Box kazananını bul
            buybox_offer = next((o for o in processed_offers if o.get('IsBuyBoxWinner')), None)
            
            if buybox_offer:
                buybox_price = float(buybox_offer['ListingPrice']['Amount'])
                currency_code = buybox_offer['ListingPrice']['CurrencyCode']
                logger.info(f"✅ Buybox Winner Found: {buybox_price} {currency_code}")
            elif processed_offers:
                # Buy Box yoksa, en düşük fiyatlı teklifi kullan
                first_offer = processed_offers[0]
                buybox_price = float(first_offer['ListingPrice']['Amount'])
                currency_code = first_offer['ListingPrice']['CurrencyCode']
                logger.info(f"✅ No Buybox Winner. Using lowest offer: {buybox_price} {currency_code}")
            
            result_data['buyboxPrice'] = buybox_price
            result_data['currencyCode'] = currency_code
            
            logger.info(f"✅ Offers processed: {len(processed_offers)}")

        except Exception as e:
            logger.error(f"❌ Error fetching or processing offers: {str(e)}")
            logger.error(traceback.format_exc())
            result_data['offers'] = []
            result_data['buyboxPrice'] = None
            result_data['currencyCode'] = None

        # 6. Fees
        logger.info("🧮 Step 6: Calculating fees...")
        if buybox_price and currency_code:
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
            logger.info("ℹ️ No price available for fee calculation, skipping.")
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
        "credentials_loaded": bool(na_credentials),
        "eu_credentials_loaded": bool(eu_credentials),
        "bsr_tables_loaded": bool(BSR_TABLES.get('US')) and bool(BSR_TABLES.get('CA')),
        "supported_marketplaces": list(MARKETPLACE_REGIONS.keys())
    })

@app.route('/get_product_details/<string:asin>', methods=['GET'])
def api_get_product_details(asin):
    logger.info(f"API request received for ASIN: {asin}")
    
    if not na_credentials and not eu_credentials:
        logger.error("Server not configured - missing credentials")
        return jsonify({"error": "Server is not configured correctly. Please check logs."}), 503

    marketplace = request.args.get('marketplace', 'US')
    logger.info(f"Marketplace: {marketplace}")
    
    # Validate marketplace
    if marketplace.upper() not in MARKETPLACE_REGIONS:
        supported = ', '.join(MARKETPLACE_REGIONS.keys())
        return jsonify({"error": f"Unsupported marketplace: {marketplace}. Supported: {supported}"}), 400
    
    try:
        data = get_full_product_details_as_json(asin, marketplace)
        
        if "error" in data:
            logger.error(f"API returning error: {data['error']}")
            return jsonify(data), 500
        
        # Add BSR data if available for the marketplace
        bsr_data = BSR_TABLES.get(marketplace.upper(), {})
        data['bsr_data'] = BSR_TABLES.get(marketplace.upper())
        data['exchange_rates'] = get_exchange_rates() # Add exchange rates to the response
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