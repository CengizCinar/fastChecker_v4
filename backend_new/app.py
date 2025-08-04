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
import re

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

# --- BSR Cache Configuration (Memory-based for Railway) ---
BSR_CACHE_DURATION = 24 * 60 * 60  # 24 hours in seconds

# BSR cache structure - Railway için memory-based
bsr_cache = {
    'data': {},
    'last_update': None,
    'cache_duration': BSR_CACHE_DURATION
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

# --- BSR Analysis Functions --- (Nihai ve Temiz Hali)

def match_category_to_bsr_table(amazon_category, bsr_table):
    """
    Match Amazon category to BSR table category with more resilience.
    Case-insensitive and handles special characters.
    """
    if not amazon_category or not bsr_table:
        return None

    def normalize_category(cat_name):
        return re.sub(r'[^a-z0-9]', '', cat_name.lower())

    normalized_amazon_cat = normalize_category(amazon_category)
    if not normalized_amazon_cat:
        return None

    for bsr_category in bsr_table.keys():
        if normalized_amazon_cat == normalize_category(bsr_category):
            logger.info(f"Category matched: '{amazon_category}' -> '{bsr_category}' (Normalized match)")
            return bsr_category

    for bsr_category in bsr_table.keys():
        if normalized_amazon_cat in normalize_category(bsr_category):
            logger.info(f"Category matched: '{amazon_category}' -> '{bsr_category}' (Partial match)")
            return bsr_category

    amazon_words = set(amazon_category.lower().split())
    for bsr_category in bsr_table.keys():
        bsr_words = set(bsr_category.lower().split())
        if amazon_words.intersection(bsr_words):
            logger.info(f"Category matched: '{amazon_category}' -> '{bsr_category}' (Word intersection)")
            return bsr_category

    logger.warning(f"Could not match Amazon category '{amazon_category}' to any BSR table category.")
    return None

def calculate_bsr_percentage(bsr_rank, bsr_category_data):
    """Calculate BSR percentage and format the display string."""
    if not bsr_rank or not bsr_category_data:
        return None

    # --- YENİ EKLENEN BÖLÜM: BSR'ı formatlama ---
    def format_bsr_for_display(rank):
        if not isinstance(rank, (int, float)):
            return "N/A"
        if rank < 1000:
            return str(rank)
        else:
            # 1000'e böl, tam sayı kısmını al ve sonuna 'k' ekle.
            return f"{int(rank / 1000)}k"
            
    formatted_rank = format_bsr_for_display(bsr_rank)
    # --- YENİ BÖLÜM SONU ---
    
    thresholds = []
    for threshold_name, threshold_value in bsr_category_data.items():
        if isinstance(threshold_value, (int, float)):
            percentage_match = re.search(r'(\d+(?:\.\d+)?)', threshold_name)
            if percentage_match:
                percentage = float(percentage_match.group(1))
                thresholds.append((percentage, threshold_value, threshold_name))
    
    thresholds.sort(key=lambda x: x[1])
    
    for percentage, threshold_value, threshold_name in thresholds:
        if bsr_rank <= threshold_value:
            return {
                'percentage': percentage,
                'threshold_name': threshold_name,
                'threshold_value': threshold_value,
                # DEĞİŞİKLİK: Formatlanmış rank kullanılıyor ve '#' kaldırıldı.
                'display': f"{formatted_rank} (Top {percentage}%)"
            }
    
    if thresholds:
        worst_threshold = thresholds[-1]
        return {
            'percentage': f">{worst_threshold[0]}",
            'threshold_name': "Beyond thresholds",
            'threshold_value': worst_threshold[1],
            # DEĞİŞİKLİK: Formatlanmış rank kullanılıyor ve '#' kaldırıldı.
            'display': f"{formatted_rank} (>Top {worst_threshold[0]}%)"
        }
    
    return {
        'percentage': "Unknown",
        'threshold_name': "No thresholds available",
        'threshold_value': 0,
        # DEĞİŞİKLİK: Formatlanmış rank kullanılıyor ve '#' kaldırıldı.
        'display': f"{formatted_rank} (Unknown %)"
    }

# --- BSR Cache Functions (Railway Memory-based) ---
def is_bsr_cache_expired():
    """Check if BSR cache has expired"""
    if not bsr_cache['last_update']:
        return True
    
    time_since_update = datetime.now() - bsr_cache['last_update']
    return time_since_update.total_seconds() > bsr_cache['cache_duration']

def refresh_bsr_data():
    """Refresh BSR data from SellerAmp and update memory cache"""
    logger.info("🔄 Refreshing BSR data from SellerAmp...")
    
    try:
        new_bsr_data = {
            'US': scrape_bsr_table_by_country(1),  # US
            'CA': scrape_bsr_table_by_country(6),  # CA
            'FR': scrape_bsr_table_by_country(4),  # France
            'DE': scrape_bsr_table_by_country(3),  # Germany
            'IT': scrape_bsr_table_by_country(8),  # Italy
            'ES': scrape_bsr_table_by_country(9),  # Spain
            'GB': scrape_bsr_table_by_country(2),  # UK
        }
        
        # Verify we got data
        success_count = 0
        for country, data in new_bsr_data.items():
            if data and isinstance(data, dict) and len(data) > 0:
                success_count += 1
                logger.info(f"✅ {country}: {len(data)} categories loaded")
            else:
                logger.warning(f"⚠️ {country}: No data loaded")
        
        if success_count >= 4:  # At least 4 countries should have data
            # Update memory cache
            bsr_cache['data'] = new_bsr_data
            bsr_cache['last_update'] = datetime.now()
            
            logger.info(f"✅ BSR data refresh completed. {success_count}/{len(new_bsr_data)} countries loaded successfully")
            logger.info(f"💾 BSR data cached in memory (Railway-compatible)")
            return True
        else:
            logger.error(f"❌ BSR data refresh failed. Only {success_count}/{len(new_bsr_data)} countries loaded")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error refreshing BSR data: {str(e)}")
        logger.error(traceback.format_exc())
        return False

def get_bsr_data():
    """Get BSR data, refresh if needed (Railway memory-based)"""
    # Check if cache is expired
    if is_bsr_cache_expired():
        cache_age = "Never loaded" if not bsr_cache['last_update'] else str(datetime.now() - bsr_cache['last_update'])
        logger.info(f"⏰ BSR cache expired (age: {cache_age}), refreshing...")
        refresh_bsr_data()
    else:
        cache_age = datetime.now() - bsr_cache['last_update']
        logger.info(f"💾 Using cached BSR data (age: {cache_age})")
    
    return bsr_cache['data']

# --- Exchange Rate Functions ---
def is_exchange_rate_cache_expired():
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
    if is_exchange_rate_cache_expired():
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

# --- Load BSR Data with Railway-compatible Caching ---
logger.info("=== APPLICATION STARTUP (Railway Environment) ===")

# Railway'de dosya sistemi geçici olduğu için sadece memory cache kullanıyoruz
logger.info("🚀 Loading BSR data for Railway deployment...")
if refresh_bsr_data():
    logger.info("✅ BSR data loaded and cached in memory")
else:
    logger.error("❌ Failed to load BSR data")
    bsr_cache['data'] = {}

# Create a global reference for backwards compatibility
BSR_TABLES = bsr_cache['data']

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
      

# --- Main Function to Get Product Details --- (Nihai ve Temiz Hali)

def get_full_product_details_as_json(asin: str, marketplace_str: str):
    logger.info(f"=== PRODUCT DETAILS REQUEST ===")
    logger.info(f"ASIN: {asin}, Marketplace: {marketplace_str}")
    
    credentials, seller_id, error = get_credentials_for_marketplace(marketplace_str)
    if error:
        logger.error(f"❌ Credential error: {error}")
        return {"error": error}

    try:
        marketplace = getattr(Marketplaces, marketplace_str.upper())
    except AttributeError:
        error_msg = f"Invalid marketplace: '{marketplace_str}'"
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
        bsr_info = {}

        # Adım 1: BİRLEŞTİRİLMİŞ VE ETKİN API ÇAĞRISI
        logger.info("🔍 Step 1: Fetching main product data, BSR, and category...")
        try:
            catalog_response = catalog_api.get_catalog_item(
                asin, 
                includedData=['summaries', 'attributes', 'identifiers', 'images', 'productTypes', 'salesRanks']
            )
            
            summary = catalog_response.payload.get('summaries', [{}])[0]
            result_data['asin'] = asin
            result_data['title'] = summary.get('itemName', 'N/A')
            result_data['brand'] = summary.get('brandName', 'N/A')
            result_data['imageUrl'] = catalog_response.payload.get('images', [{}])[0].get('images', [{}])[0].get('link')
            result_data['ean'] = next((i['identifier'] for i in catalog_response.payload.get('identifiers', [{}])[0].get('identifiers', []) if i['identifierType'] == 'EAN'), 'N/A')
            
            logger.info(f"Product: {result_data['title'][:50]}...")

            sales_ranks_data = catalog_response.payload.get('salesRanks', [])
            if sales_ranks_data:
                ranks_list = sales_ranks_data[0].get('ranks', [])
                if ranks_list:
                    main_rank_info = max(ranks_list, key=lambda x: x.get('rank', 0))
                    bsr_info = {
                        'rank': main_rank_info.get('rank'),
                        'category': main_rank_info.get('title')
                    }
                    logger.info(f"✅ BSR and Category Found: #{bsr_info.get('rank')} in '{bsr_info.get('category')}'")
            
            result_data['bsr_info'] = bsr_info if bsr_info else None

            attributes_data = catalog_response.payload.get('attributes', {})
            package_dims = attributes_data.get('item_package_dimensions', [{}])[0]
            if package_dims and 'value' in package_dims.get('length', {}):
                length = package_dims['length']['value'] * 2.54 if package_dims['length'].get('unit', '').lower() == 'inches' else package_dims['length']['value']
                width = package_dims['width']['value'] * 2.54 if package_dims['width'].get('unit', '').lower() == 'inches' else package_dims['width']['value']
                height = package_dims['height']['value'] * 2.54 if package_dims['height'].get('unit', '').lower() == 'inches' else package_dims['height']['value']
                result_data['dimensions'] = f"{length:.1f} x {width:.1f} x {height:.1f} cm"
            else:
                result_data['dimensions'] = "N/A"
            
            package_weight = attributes_data.get('item_package_weight', [{}])[0]
            if package_weight and 'value' in package_weight:
                weight_value = package_weight['value']
                weight_unit = package_weight.get('unit', '').lower()
                weight_gr = weight_value * 453.592 if weight_unit in ['pounds', 'pound'] else (weight_value * 1000 if weight_unit in ['kilograms', 'kg'] else weight_value)
                result_data['packageWeight'] = f"{weight_gr:.0f} gr"
            else:
                result_data['packageWeight'] = "N/A"
        except Exception as e:
            logger.error(f"❌ Error in main catalog/BSR step: {str(e)}")
            result_data.update({'title': 'N/A', 'brand': 'N/A', 'bsr_info': None})

        # Adım 2: KISITLAMALAR
        logger.info("🚫 Step 2: Checking selling restrictions...")
        try:
            restrictions_response = restrictions_api.get_listings_restrictions(asin=asin, sellerId=seller_id, conditionType='new_new')
            restrictions = restrictions_response.payload.get('restrictions', [])
            result_data['isSellable'] = not bool(restrictions)
            result_data['restrictionReasons'] = [reason.get('message') for r in restrictions for reason in r.get('reasons', [])]
        except Exception as e:
            logger.error(f"❌ Error checking restrictions: {str(e)}")
            result_data['isSellable'] = None
        
        # Adım 3: TEKLİFLER
        logger.info("💰 Step 3: Fetching offers and pricing...")
        buybox_price = None
        currency_code = None
        try:
            offers_response = products_api.get_item_offers(asin, "New", MarketplaceId=marketplace.marketplace_id)
            offers = offers_response.payload.get('Offers', [])
            result_data['offers'] = sorted([o for o in offers], key=lambda x: float(x.get('ListingPrice', {}).get('Amount', float('inf'))))
            
            buybox_offer = next((o for o in result_data['offers'] if o.get('IsBuyBoxWinner')), None)
            if buybox_offer:
                buybox_price = float(buybox_offer['ListingPrice']['Amount'])
                currency_code = buybox_offer['ListingPrice']['CurrencyCode']
            elif result_data['offers']:
                buybox_price = float(result_data['offers'][0]['ListingPrice']['Amount'])
                currency_code = result_data['offers'][0]['ListingPrice']['CurrencyCode']
            
            result_data['buyboxPrice'] = buybox_price
            result_data['currencyCode'] = currency_code
        except Exception as e:
            logger.error(f"❌ Error fetching offers: {str(e)}")

        # Adım 4: BSR ANALİZİ
        logger.info("🎯 Step 4: Performing BSR Analysis...")
        if result_data.get('bsr_info'):
            bsr_data = BSR_TABLES.get(marketplace_str.upper(), {})
            matched_category = match_category_to_bsr_table(bsr_info['category'], bsr_data)
            if matched_category:
                bsr_percentage = calculate_bsr_percentage(bsr_info['rank'], bsr_data[matched_category])
                result_data['bsr_analysis'] = { 'enhanced_display': bsr_percentage.get('display') }
            else:
                result_data['bsr_analysis'] = {'enhanced_display': f"#{bsr_info.get('rank')} (Category not in BSR table)"}
        else:
            result_data['bsr_analysis'] = {'enhanced_display': "BSR not available"}

        # Adım 5: ÜCRETLER (DETAYLI PARSING İLE)
        logger.info("🧮 Step 5: Calculating fees...")
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
                else:
                    result_data.update({'totalFees': None, 'referralFee': None, 'fbaFee': None, 'netProfit': None})
            except Exception as e:
                logger.error(f"❌ Error calculating fees: {str(e)}")
        else:
            result_data.update({'totalFees': None, 'referralFee': None, 'fbaFee': None, 'netProfit': None})

        # Adım 6: PARA BİRİMİ ÇEVRİMİ (EKSİKSİZ)
        logger.info("💱 Step 6: Adding currency conversion data...")
        if buybox_price and currency_code:
            result_data['originalCurrency'] = currency_code
            result_data['originalPrice'] = buybox_price
            result_data['convertedPrices'] = get_converted_prices(buybox_price, currency_code)
            result_data['exchangeRates'] = get_exchange_rates_for_currency(currency_code)
            if result_data.get('totalFees'):
                result_data['convertedTotalFees'] = get_converted_prices(result_data['totalFees'], currency_code)
            if result_data.get('netProfit'):
                result_data['convertedNetProfit'] = get_converted_prices(result_data['netProfit'], currency_code)
        
        result_data['bsr_data'] = BSR_TABLES.get(marketplace_str.upper(), {})
        logger.info("✅ Product details fetched successfully.")
        return result_data

    except SellingApiException as e:
        error_message = str(e.payload or e)
        logger.error(f"❌ Amazon SP API Error: {error_message}")
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
        "message": "FastChecker Backend with Enhanced BSR Analysis is running on Railway!",
        "timestamp": datetime.now().isoformat(),
        "deployment_platform": "Railway",
        "cache_type": "Memory-based (Railway compatible)",
        "features": [
            "Amazon SP-API BSR extraction",
            "BSR percentage calculation", 
            "Category matching",
            "Enhanced BSR display format"
        ],
        "credentials_loaded": bool(na_credentials),
        "eu_credentials_loaded": bool(eu_credentials),
        "bsr_tables_loaded": bool(bsr_cache['data']),
        "bsr_cache_status": {
            "last_update": bsr_cache['last_update'].isoformat() if bsr_cache['last_update'] else None,
            "cache_expired": is_bsr_cache_expired(),
            "available_countries": list(bsr_cache['data'].keys()),
            "cache_storage": "Memory (Railway ephemeral file system)"
        },
        "supported_marketplaces": list(MARKETPLACE_REGIONS.keys()),
        "exchange_rate_enabled": bool(os.environ.get('EXCHANGE_RATE_API_KEY')),
        "exchange_rate_cache_status": {
            "last_update": exchange_rates_cache['last_update'].isoformat() if exchange_rates_cache['last_update'] else None,
            "cached_pairs": len(exchange_rates_cache['rates']),
            "supported_currencies": SUPPORTED_CURRENCIES,
            "cache_expired": is_exchange_rate_cache_expired()
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
        
        # Minimal logging for Railway
        logger.info(f"✅ API request completed successfully for ASIN: {asin}")
        
        # Log enhanced BSR results
        if data.get('bsr_analysis') and data['bsr_analysis'].get('enhanced_display'):
            logger.info(f"🎯 Enhanced BSR Display: {data['bsr_analysis']['enhanced_display']}")
        
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
        if is_exchange_rate_cache_expired():
            logger.info("Cache expired, refreshing exchange rates...")
            success = fetch_all_exchange_rates()
            if not success:
                logger.warning("Failed to refresh exchange rates, using cached data")
        
        return jsonify({
            "status": "success",
            "supported_currencies": SUPPORTED_CURRENCIES,
            "exchange_rates": exchange_rates_cache['rates'],
            "last_update": exchange_rates_cache['last_update'].isoformat() if exchange_rates_cache['last_update'] else None,
            "cache_expired": is_exchange_rate_cache_expired(),
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
                "cache_storage": "Memory (Railway compatible)"
            },
            "deployment_platform": "Railway",
            "enhanced_features": [
                "BSR percentage calculation",
                "Category matching algorithm",
                "Enhanced display format"
            ],
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
            
            # ENHANCED: Show BSR analysis capabilities
            if found_common:
                sample_category = list(found_common.keys())[0]
                sample_bsr_data = found_common[sample_category]
                sample_analysis = calculate_bsr_percentage(5000, sample_bsr_data)
                result["sample_bsr_analysis"] = {
                    "category": sample_category,
                    "sample_rank": 5000,
                    "analysis_result": sample_analysis
                }
            
        else:
            result["error"] = f"No BSR data loaded for marketplace: {marketplace}"
            result["available_marketplaces"] = list(current_bsr_tables.keys())
        
        logger.info(f"BSR Debug completed for {marketplace}: {len(bsr_data)} entries")
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"❌ Error in BSR debug endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route('/bsr_refresh', methods=['POST'])
def api_force_bsr_refresh():
    """Force refresh BSR data (Railway memory-based)"""
    logger.info("🔄 Manual BSR refresh requested (Railway)")
    
    try:
        if refresh_bsr_data():
            # Update global BSR_TABLES for backwards compatibility
            global BSR_TABLES
            BSR_TABLES = bsr_cache['data']
            
            return jsonify({
                "status": "success",
                "message": "BSR data refreshed successfully in memory (Railway)",
                "last_update": bsr_cache['last_update'].isoformat(),
                "available_countries": list(bsr_cache['data'].keys()),
                "cache_storage": "Memory (Railway compatible)",
                "enhanced_features": [
                    "BSR percentage calculation ready",
                    "Category matching algorithms updated"
                ],
                "timestamp": datetime.now().isoformat()
            })
        else:
            return jsonify({
                "status": "error",
                "message": "Failed to refresh BSR data",
                "cache_storage": "Memory (Railway compatible)",
                "timestamp": datetime.now().isoformat()
            }), 500
            
    except Exception as e:
        logger.error(f"❌ Error in BSR refresh endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route('/cache_status', methods=['GET'])
def api_cache_status():
    """Get detailed cache status for Railway monitoring"""
    logger.info("Cache status API request received")
    
    try:
        return jsonify({
            "deployment_platform": "Railway",
            "cache_type": "Memory-based (ephemeral file system compatible)",
            "enhanced_features": [
                "Amazon SP-API BSR extraction",
                "BSR percentage calculation",
                "Category matching algorithms",
                "Enhanced BSR display format"
            ],
            "bsr_cache": {
                "status": "active" if bsr_cache['data'] else "empty",
                "last_update": bsr_cache['last_update'].isoformat() if bsr_cache['last_update'] else None,
                "cache_expired": is_bsr_cache_expired(),
                "countries_loaded": list(bsr_cache['data'].keys()),
                "total_categories": sum(len(data) for data in bsr_cache['data'].values()),
                "cache_duration_hours": BSR_CACHE_DURATION / 3600
            },
            "exchange_rate_cache": {
                "status": "active" if exchange_rates_cache['rates'] else "empty",
                "last_update": exchange_rates_cache['last_update'].isoformat() if exchange_rates_cache['last_update'] else None,
                "cache_expired": is_exchange_rate_cache_expired(),
                "cached_pairs": len(exchange_rates_cache['rates']),
                "supported_currencies": SUPPORTED_CURRENCIES,
                "cache_duration_hours": exchange_rates_cache['cache_duration'] / 3600
            },
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"❌ Error in cache status endpoint: {str(e)}")
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
    logger.info(f"Starting Flask server with Enhanced BSR Analysis on Railway (port {port})")
    app.run(host='0.0.0.0', port=port, debug=False)