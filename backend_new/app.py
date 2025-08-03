import os
import json
import logging
import traceback
import requests
from datetime import datetime, timedelta
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

# --- Exchange Rate Configuration ---
SUPPORTED_CURRENCIES = ['EUR', 'USD', 'GBP', 'CAD']
EXCHANGE_RATE_API_BASE = "https://v6.exchangerate-api.com/v6"

# Exchange rate cache
exchange_rates_cache = {
    'rates': {},
    'last_update': None,
    'cache_duration': 24 * 60 * 60  # 24 hours in seconds
}

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

# --- Exchange Rate Functions ---
def is_cache_expired():
    """Check if exchange rate cache has expired"""
    if not exchange_rates_cache['last_update']:
        return True
    
    time_since_update = datetime.now() - exchange_rates_cache['last_update']
    return time_since_update.total_seconds() > exchange_rates_cache['cache_duration']

def fetch_all_exchange_rates():
    """Fetch all exchange rates from API and update cache"""
    logger.info("🔄 Fetching fresh exchange rates from API...")
    
    # Get API key from environment
    api_key = os.environ.get('EXCHANGE_RATE_API_KEY')
    if not api_key:
        logger.error("❌ EXCHANGE_RATE_API_KEY not found in environment variables")
        return False
    
    new_rates = {}
    failed_requests = 0
    
    # Fetch rates for all currency pairs
    for base_currency in SUPPORTED_CURRENCIES:
        for target_currency in SUPPORTED_CURRENCIES:
            if base_currency == target_currency:
                continue
                
            try:
                url = f"{EXCHANGE_RATE_API_BASE}/{api_key}/pair/{base_currency}/{target_currency}"
                logger.info(f"📡 Fetching {base_currency} -> {target_currency}")
                
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                
                data = response.json()
                
                if data.get('result') == 'success':
                    rate_key = f"{base_currency}_{target_currency}"
                    new_rates[rate_key] = {
                        'rate': data['conversion_rate'],
                        'last_update': data.get('time_last_update_utc'),
                        'next_update': data.get('time_next_update_utc')
                    }
                    logger.info(f"✅ {base_currency}/{target_currency}: {data['conversion_rate']}")
                else:
                    logger.error(f"❌ API Error for {base_currency}/{target_currency}: {data.get('error-type', 'Unknown error')}")
                    failed_requests += 1
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"❌ Network error fetching {base_currency}/{target_currency}: {str(e)}")
                failed_requests += 1
            except Exception as e:
                logger.error(f"❌ Unexpected error fetching {base_currency}/{target_currency}: {str(e)}")
                failed_requests += 1
    
    # Update cache if we got at least some rates
    if new_rates and failed_requests < len(new_rates):
        exchange_rates_cache['rates'] = new_rates
        exchange_rates_cache['last_update'] = datetime.now()
        logger.info(f"✅ Exchange rates updated successfully! {len(new_rates)} rates cached, {failed_requests} failed")
        return True
    else:
        logger.error(f"❌ Failed to fetch exchange rates. {failed_requests} failures out of {len(SUPPORTED_CURRENCIES) * (len(SUPPORTED_CURRENCIES) - 1)} attempts")
        return False

def get_exchange_rate(from_currency, to_currency):
    """Get exchange rate from cache, refresh if needed"""
    if from_currency == to_currency:
        return 1.0
    
    # Check if cache needs refresh
    if is_cache_expired():
        logger.info("💱 Exchange rate cache expired, refreshing...")
        fetch_all_exchange_rates()
    
    # Get rate from cache
    rate_key = f"{from_currency}_{to_currency}"
    rate_info = exchange_rates_cache['rates'].get(rate_key)
    
    if rate_info:
        return rate_info['rate']
    else:
        logger.warning(f"⚠️ No exchange rate found for {from_currency} -> {to_currency}")
        return None

def convert_currency(amount, from_currency, to_currency):
    """Convert amount from one currency to another"""
    if not amount or from_currency == to_currency:
        return amount
    
    rate = get_exchange_rate(from_currency, to_currency)
    if rate:
        converted = float(amount) * rate
        logger.info(f"💰 Converted {amount} {from_currency} -> {converted:.2f} {to_currency} (rate: {rate})")
        return round(converted, 2)
    else:
        logger.warning(f"⚠️ Could not convert {amount} from {from_currency} to {to_currency}")
        return None

def get_converted_prices(original_amount, original_currency):
    """Get prices converted to all supported currencies"""
    if not original_amount:
        return {}
    
    converted_prices = {}
    for target_currency in SUPPORTED_CURRENCIES:
        if target_currency != original_currency:
            converted_price = convert_currency(original_amount, original_currency, target_currency)
            if converted_price is not None:
                converted_prices[target_currency] = converted_price
    
    return converted_prices

def get_exchange_rates_for_currency(base_currency):
    """Get all exchange rates for a base currency"""
    rates = {}
    for target_currency in SUPPORTED_CURRENCIES:
        if target_currency != base_currency:
            rate = get_exchange_rate(base_currency, target_currency)
            if rate is not None:
                rates[f"{base_currency}_{target_currency}"] = rate
    return rates

# --- Load BSR Data with Logging ---
logger.info("=== APPLICATION STARTUP ===")
logger.info("Loading BSR tables from SellerAmp...")
try:
    BSR_TABLES = {
 'US': scrape_bsr_table_by_country(1), # US
 'CA': scrape_bsr_table_by_country(6), # CA
 'FR': scrape_bsr_table_by_country(4), # France
 'DE': scrape_bsr_table_by_country(3), # Germany
 'IT': scrape_bsr_table_by_country(8), # Italy
 'ES': scrape_bsr_table_by_country(9), # Spain
 'GB': scrape_bsr_table_by_country(2), # UK
    }
    
    # DETAILED BSR DATA LOGGING
    logger.info("=== BSR DATA LOADED ===")
    for country, data in BSR_TABLES.items():
        logger.info(f"📊 {country} BSR Table - Total entries: {len(data)}")
        
        # Log ALL entries to see complete structure
        if data:
            logger.info(f"🔍 {country} - ALL BSR categories:")
            for i, (key, value) in enumerate(data.items()):
                logger.info(f"   {i+1:2d}. {key}: {value}")
            logger.info(f"--- End of {country} BSR data ---")
        else:
            logger.warning(f"⚠️ {country} - No BSR data loaded!")
    
    logger.info(f"BSR tables loaded successfully. US entries: {len(BSR_TABLES.get('US', {}))}, CA entries: {len(BSR_TABLES.get('CA', {}))}")
except Exception as e:
    logger.error(f"Error loading BSR tables: {str(e)}")
    logger.error(traceback.format_exc())
    BSR_TABLES = {'US': {}, 'CA': {}}

# --- Load Exchange Rates on Startup ---
logger.info("Loading initial exchange rates...")
if os.environ.get('EXCHANGE_RATE_API_KEY'):
    fetch_all_exchange_rates()
else:
    logger.warning("⚠️ EXCHANGE_RATE_API_KEY not found. Currency conversion will be disabled.")

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
    logger.error("Optional environment variables for currency conversion:")
    logger.error("- EXCHANGE_RATE_API_KEY")
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

        # 7. Currency Conversion (NEW FEATURE)
        logger.info("💱 Step 7: Adding currency conversion data...")
        try:
            if buybox_price and currency_code and currency_code in SUPPORTED_CURRENCIES:
                # Add converted prices
                result_data['originalCurrency'] = currency_code
                result_data['originalPrice'] = buybox_price
                result_data['convertedPrices'] = get_converted_prices(buybox_price, currency_code)
                result_data['exchangeRates'] = get_exchange_rates_for_currency(currency_code)
                result_data['lastExchangeRateUpdate'] = exchange_rates_cache['last_update'].isoformat() if exchange_rates_cache['last_update'] else None
                
                # Also convert fees if available
                if result_data.get('totalFees'):
                    result_data['convertedTotalFees'] = get_converted_prices(result_data['totalFees'], currency_code)
                if result_data.get('netProfit'):
                    result_data['convertedNetProfit'] = get_converted_prices(result_data['netProfit'], currency_code)
                
                logger.info(f"✅ Currency conversion added. Base: {currency_code}, Converted to: {list(result_data['convertedPrices'].keys())}")
            else:
                logger.info(f"ℹ️ Currency conversion skipped. Price: {buybox_price}, Currency: {currency_code}")
                result_data['originalCurrency'] = currency_code
                result_data['originalPrice'] = buybox_price
                result_data['convertedPrices'] = {}
                result_data['exchangeRates'] = {}
                result_data['lastExchangeRateUpdate'] = None
                
        except Exception as e:
            logger.error(f"❌ Error in currency conversion: {str(e)}")
            logger.error(traceback.format_exc())
            result_data['convertedPrices'] = {}
            result_data['exchangeRates'] = {}
            result_data['lastExchangeRateUpdate'] = None

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
        "bsr_tables_loaded": bool(bsr_cache['data']),
        "bsr_cache_status": {
            "last_update": bsr_cache['last_update'].isoformat() if bsr_cache['last_update'] else None,
            "cache_expired": is_bsr_cache_expired(),
            "available_countries": list(bsr_cache['data'].keys()),
            "cache_file_exists": os.path.exists(BSR_CACHE_FILE)
        },
        "supported_marketplaces": list(MARKETPLACE_REGIONS.keys()),
        "exchange_rate_enabled": bool(os.environ.get('EXCHANGE_RATE_API_KEY')),
        "exchange_rate_cache_status": {
            "last_update": exchange_rates_cache['last_update'].isoformat() if exchange_rates_cache['last_update'] else None,
            "cached_pairs": len(exchange_rates_cache['rates']),
            "supported_currencies": SUPPORTED_CURRENCIES,
            "cache_expired": is_cache_expired()
        }
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
        data['bsr_data'] = bsr_data
        
        # LOG BSR DATA FOR THIS SPECIFIC REQUEST
        logger.info("=== BSR DATA FOR THIS REQUEST ===")
        logger.info(f"📊 Marketplace: {marketplace.upper()}")
        logger.info(f"📊 BSR Data Available: {'Yes' if bsr_data else 'No'}")
        logger.info(f"📊 BSR Data Entries: {len(bsr_data)}")
        
        if bsr_data:
            # Log first few entries for this marketplace
            logger.info(f"🔍 Sample BSR entries for {marketplace.upper()}:")
            for i, (key, value) in enumerate(list(bsr_data.items())[:3]):
                logger.info(f"   BSR Entry {i+1}: '{key}' -> '{value}'")
                
            # Check if we have specific categories
            sample_categories = ['Electronics', 'Books', 'Home & Kitchen', 'Toys & Games', 'Sports & Outdoors']
            found_categories = []
            for category in sample_categories:
                if category in bsr_data:
                    found_categories.append(f"{category}: {bsr_data[category]}")
            
            if found_categories:
                logger.info(f"🎯 Found common categories in {marketplace.upper()}: {', '.join(found_categories[:3])}")
            else:
                logger.info(f"⚠️ No common categories found in {marketplace.upper()} BSR data")
        else:
            logger.warning(f"❌ No BSR data available for marketplace: {marketplace.upper()}")
        
        logger.info(f"✅ API request completed successfully for ASIN: {asin}")
        return jsonify(data)
        
    except Exception as e:
        logger.error(f"❌ Unexpected error in API endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route('/exchange_rates', methods=['GET'])
def api_get_exchange_rates():
    """Get current exchange rates"""
    logger.info("Exchange rates API request received")
    
    if not os.environ.get('EXCHANGE_RATE_API_KEY'):
        return jsonify({"error": "Exchange rate API not configured"}), 503
    
    try:
        # Refresh rates if expired
        if is_cache_expired():
            logger.info("Cache expired, refreshing exchange rates...")
            success = fetch_all_exchange_rates()
            if not success:
                logger.warning("Failed to refresh exchange rates, using cached data")
        
        return jsonify({
            "status": "success",
            "supported_currencies": SUPPORTED_CURRENCIES,
            "exchange_rates": exchange_rates_cache['rates'],
            "last_update": exchange_rates_cache['last_update'].isoformat() if exchange_rates_cache['last_update'] else None,
            "cache_expired": is_cache_expired(),
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"❌ Error in exchange rates endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route('/convert', methods=['GET'])
def api_convert_currency():
    """Convert currency amount"""
    logger.info("Currency conversion API request received")
    
    if not os.environ.get('EXCHANGE_RATE_API_KEY'):
        return jsonify({"error": "Exchange rate API not configured"}), 503
    
    try:
        # Get parameters
        amount = request.args.get('amount', type=float)
        from_currency = request.args.get('from', '').upper()
        to_currency = request.args.get('to', '').upper()
        
        # Validate parameters
        if not amount:
            return jsonify({"error": "Amount parameter is required"}), 400
        if not from_currency or from_currency not in SUPPORTED_CURRENCIES:
            return jsonify({"error": f"Invalid 'from' currency. Supported: {SUPPORTED_CURRENCIES}"}), 400
        if not to_currency or to_currency not in SUPPORTED_CURRENCIES:
            return jsonify({"error": f"Invalid 'to' currency. Supported: {SUPPORTED_CURRENCIES}"}), 400
        
        # Convert currency
        converted_amount = convert_currency(amount, from_currency, to_currency)
        exchange_rate = get_exchange_rate(from_currency, to_currency)
        
        if converted_amount is None or exchange_rate is None:
            return jsonify({"error": f"Could not convert from {from_currency} to {to_currency}"}), 500
        
        return jsonify({
            "status": "success",
            "original_amount": amount,
            "original_currency": from_currency,
            "converted_amount": converted_amount,
            "target_currency": to_currency,
            "exchange_rate": exchange_rate,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"❌ Error in currency conversion endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route('/bsr_debug/<string:marketplace>', methods=['GET'])
def api_debug_bsr_data(marketplace):
    """Debug endpoint to check BSR data for a specific marketplace"""
    logger.info(f"BSR Debug request for marketplace: {marketplace}")
    
    marketplace = marketplace.upper()
    
    if marketplace not in MARKETPLACE_REGIONS:
        supported = ', '.join(MARKETPLACE_REGIONS.keys())
        return jsonify({"error": f"Unsupported marketplace: {marketplace}. Supported: {supported}"}), 400
    
    try:
        # Get fresh BSR data (will use cache if still valid)
        current_bsr_tables = get_bsr_data()
        bsr_data = current_bsr_tables.get(marketplace, {})
        
        # Detailed BSR analysis
        result = {
            "marketplace": marketplace,
            "bsr_data_available": bool(bsr_data),
            "total_entries": len(bsr_data),
            "cache_status": {
                "last_update": bsr_cache['last_update'].isoformat() if bsr_cache['last_update'] else None,
                "cache_expired": is_bsr_cache_expired(),
                "cache_file_exists": os.path.exists(BSR_CACHE_FILE)
            },
            "timestamp": datetime.now().isoformat()
        }
        
        if bsr_data:
            # Get first 10 entries
            sample_entries = dict(list(bsr_data.items())[:10])
            result["sample_entries"] = sample_entries
            
            # Get all keys to see structure
            all_keys = list(bsr_data.keys())
            result["all_categories"] = all_keys[:50]  # First 50 categories
            result["total_categories"] = len(all_keys)
            
            # Look for common patterns
            common_categories = ['Electronics', 'Books', 'Home & Kitchen', 'Toys & Games', 'Sports & Outdoors', 'Clothing, Shoes & Jewelry', 'Health & Personal Care']
            found_common = {}
            for cat in common_categories:
                if cat in bsr_data:
                    found_common[cat] = bsr_data[cat]
            result["common_categories_found"] = found_common
            
        else:
            result["error"] = f"No BSR data loaded for marketplace: {marketplace}"
            result["available_marketplaces"] = list(current_bsr_tables.keys())
        
        logger.info(f"BSR Debug completed for {marketplace}: {len(bsr_data)} entries")
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"❌ Error in BSR debug endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"error": f"Server error: {str(e)}"}), 500

# NEW ENDPOINT TO FORCE BSR REFRESH
@app.route('/bsr_refresh', methods=['POST'])
def api_force_bsr_refresh():
    """Force refresh BSR data"""
    logger.info("🔄 Manual BSR refresh requested")
    
    try:
        if refresh_bsr_data():
            # Update global BSR_TABLES
            global BSR_TABLES
            BSR_TABLES = bsr_cache['data']
            
            return jsonify({
                "status": "success",
                "message": "BSR data refreshed successfully",
                "last_update": bsr_cache['last_update'].isoformat(),
                "available_countries": list(bsr_cache['data'].keys()),
                "timestamp": datetime.now().isoformat()
            })
        else:
            return jsonify({
                "status": "error",
                "message": "Failed to refresh BSR data",
                "timestamp": datetime.now().isoformat()
            }), 500
            
    except Exception as e:
        logger.error(f"❌ Error in BSR refresh endpoint: {str(e)}")
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