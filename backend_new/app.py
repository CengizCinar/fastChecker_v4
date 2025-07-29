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

# --- Currency API Configuration ---
CURRENCY_API_KEY = os.getenv('CURRENCY_API_KEY')
CURRENCY_CACHE_FILE = 'currency_cache.json'
CURRENCY_CACHE_DURATION = 24  # hours

def load_currency_cache():
    """Load currency exchange rates from cache file"""
    try:
        if os.path.exists(CURRENCY_CACHE_FILE):
            with open(CURRENCY_CACHE_FILE, 'r') as f:
                cache_data = json.load(f)
                cache_time = datetime.fromisoformat(cache_data.get('timestamp', '2000-01-01'))
                if datetime.now() - cache_time < timedelta(hours=CURRENCY_CACHE_DURATION):
                    return cache_data.get('rates', {})
    except Exception as e:
        logger.warning(f"Could not load currency cache: {e}")
    return {}

def save_currency_cache(rates):
    """Save currency exchange rates to cache file"""
    try:
        cache_data = {
            'timestamp': datetime.now().isoformat(),
            'rates': rates
        }
        with open(CURRENCY_CACHE_FILE, 'w') as f:
            json.dump(cache_data, f)
        logger.info("Currency cache saved successfully")
    except Exception as e:
        logger.error(f"Could not save currency cache: {e}")

def get_exchange_rates():
    """Get current exchange rates from API or cache"""
    if not CURRENCY_API_KEY:
        logger.error("CURRENCY_API_KEY not configured - currency conversion disabled")
        return {}
    
    # Try to load from cache first
    cached_rates = load_currency_cache()
    if cached_rates:
        logger.info("Using cached exchange rates")
        return cached_rates
    
    # Fetch from API if cache is expired or empty
    try:
        logger.info("Fetching exchange rates from API...")
        url = f"https://v6.exchangerate-api.com/v6/{CURRENCY_API_KEY}/latest/USD"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        if data.get('result') == 'success':
            rates = data.get('conversion_rates', {})
            save_currency_cache(rates)
            logger.info("Exchange rates fetched and cached successfully")
            return rates
        else:
            logger.error(f"Currency API error: {data.get('error-type', 'Unknown error')}")
            return {}
    except Exception as e:
        logger.error(f"Could not fetch exchange rates: {e}")
        return {}

def convert_currency(amount, from_currency, to_currency):
    """Convert amount from one currency to another"""
    if from_currency == to_currency:
        return amount
    
    rates = get_exchange_rates()
    if not rates:
        logger.error("No exchange rates available - currency conversion failed")
        return None
    
    # Convert to USD first, then to target currency
    try:
        if from_currency == 'USD':
            usd_amount = amount
        else:
            from_rate = rates.get(from_currency)
            if not from_rate:
                logger.error(f"Exchange rate not found for {from_currency}")
                return None
            usd_amount = amount / from_rate
        
        if to_currency == 'USD':
            return usd_amount
        else:
            to_rate = rates.get(to_currency)
            if not to_rate:
                logger.error(f"Exchange rate not found for {to_currency}")
                return None
            return usd_amount * to_rate
    except Exception as e:
        logger.error(f"Currency conversion error: {e}")
        return None

# --- Logging Configuration ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Flask App Configuration ---
app = Flask(__name__)
CORS(app)

# --- Marketplace Configuration ---
MARKETPLACE_REGIONS = {
    'US': {'region': 'NA', 'marketplace_id': 'ATVPDKIKX0DER'},
    'CA': {'region': 'NA', 'marketplace_id': 'A2EUQ1WTGCTBG2'},
    'MX': {'region': 'NA', 'marketplace_id': 'A1AM78C64UM0Y8'},
    'DE': {'region': 'EU', 'marketplace_id': 'A1PA6795UKMFR9'},
    'GB': {'region': 'EU', 'marketplace_id': 'A1F83G8C2ARO7P'},
    'FR': {'region': 'EU', 'marketplace_id': 'A13V1IB3VIYZZH'},
    'IT': {'region': 'EU', 'marketplace_id': 'A11IBZPNXEPRB4'},
    'ES': {'region': 'EU', 'marketplace_id': 'A1RKKUPIHCS9HS'},
    'NL': {'region': 'EU', 'marketplace_id': 'A1805FZKASX7XG'},
    'SE': {'region': 'EU', 'marketplace_id': 'A2NODRKZPJ3EIB'},
    'PL': {'region': 'EU', 'marketplace_id': 'A1C3SOZRARQ6R3'},
    'BE': {'region': 'EU', 'marketplace_id': 'AMEN7PMS3EDWL'}
}

# --- Credential Loading ---
try:
    # Shared AWS credentials
    aws_access_key = os.environ['AWS_ACCESS_KEY_ID']
    aws_secret_key = os.environ['AWS_SECRET_ACCESS_KEY']
    
    # NA credentials
    na_credentials = {
        'refresh_token': os.environ['AMAZON_REFRESH_TOKEN'],
        'lwa_app_id': os.environ['AMAZON_LWA_APP_ID'],
        'lwa_client_secret': os.environ['AMAZON_LWA_CLIENT_SECRET'],
        'aws_access_key': aws_access_key,
        'aws_secret_key': aws_secret_key
    }
    na_seller_id = os.environ['AMAZON_SELLER_ID']
    
    # EU credentials (optional)
    eu_credentials = None
    eu_seller_id = None
    if 'EU_REFRESH_TOKEN' in os.environ:
        eu_credentials = {
            'refresh_token': os.environ['EU_REFRESH_TOKEN'],
            'lwa_app_id': os.environ['EU_LWA_APP_ID'],
            'lwa_client_secret': os.environ['EU_LWA_CLIENT_SECRET'],
            'aws_access_key': aws_access_key,
            'aws_secret_key': aws_secret_key
        }
        eu_seller_id = os.environ['EU_SELLER_ID']
    
    logger.info("✅ All credentials loaded successfully")
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
    logger.error("Optional environment variable for currency conversion:")
    logger.error("- CURRENCY_API_KEY")
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

# --- Exchange Rate Conversion ---
EXCHANGE_RATE_API_KEY = os.environ.get('EXCHANGE_RATE_API_KEY')
exchange_rate_cache = {}
cache_expiry = timedelta(hours=4) # Cache rates for 4 hours

def get_exchange_rates(base_currency):
    """Fetches exchange rates for a given base currency and caches them."""
    global exchange_rate_cache
    now = datetime.now()

    if base_currency in exchange_rate_cache:
        cached_data = exchange_rate_cache[base_currency]
        if now < cached_data['expiry']:
            logger.info(f"Using cached exchange rates for {base_currency}")
            return cached_data['rates']

    if not EXCHANGE_RATE_API_KEY:
        logger.error("EXCHANGE_RATE_API_KEY environment variable not set.")
        return None

    try:
        logger.info(f"Fetching new exchange rates for {base_currency} from API...")
        url = f"https://v6.exchangerate-api.com/v6/{EXCHANGE_RATE_API_KEY}/latest/{base_currency}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get('result') == 'success':
            rates = data['conversion_rates']
            exchange_rate_cache[base_currency] = {
                'rates': rates,
                'expiry': now + cache_expiry
            }
            logger.info(f"Successfully fetched and cached new exchange rates for {base_currency}.")
            return rates
        else:
            logger.error(f"Exchange rate API returned an error: {data.get('error-type')}")
            return None
    except requests.RequestException as e:
        logger.error(f"Error fetching exchange rates: {e}")
        return None



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
        catalog_api = CatalogItems(credentials=credentials, marketplace=marketplace)
        restrictions_api = ListingsRestrictions(credentials=credentials, marketplace=marketplace)
        products_api = Products(credentials=credentials, marketplace=marketplace)
        fees_api = ProductFees(credentials=credentials, marketplace=marketplace)
        logger.info("✅ All APIs initialized successfully")

        result_data = {}
        buybox_price = None
        currency_code = None

        # 1. Catalog Info (Attributes)
        logger.info("🔍 Step 1: Fetching catalog attributes...")
        catalog_response_attributes = catalog_api.get_catalog_item(asin, includedData=['summaries', 'attributes'])
        summary = catalog_response_attributes.payload.get('summaries', [{}])[0]
        result_data['asin'] = asin
        result_data['title'] = summary.get('itemName', 'N/A')
        result_data['brand'] = summary.get('brand', 'N/A')

        # 2. Offers and Pricing
        logger.info("💰 Step 2: Fetching offers and pricing...")
        offers_response = products_api.get_item_offers(asin, "New", MarketplaceId=marketplace.marketplace_id)
        offers = offers_response.payload.get('Offers', [])
        buybox_offer = next((o for o in offers if o.get('IsBuyBoxWinner')), None)
        if buybox_offer:
            buybox_price = float(buybox_offer['ListingPrice']['Amount'])
            currency_code = buybox_offer['ListingPrice']['CurrencyCode']
        result_data['buyboxPrice'] = buybox_price
        result_data['currencyCode'] = currency_code

        # 3. Fees Calculation
        logger.info("🧮 Step 3: Calculating fees...")
        if buybox_price and currency_code:
            fees_request_payload = [{
                'IdType': 'ASIN',
                'IdValue': asin,
                'PriceToEstimateFees': {
                    'ListingPrice': {
                        'CurrencyCode': currency_code,
                        'Amount': buybox_price
                    }
                },
                'MarketplaceId': marketplace.marketplace_id,
                'IsFulfillmentByAmazon': True
            }]
            fees_response = fees_api.get_my_fees_estimate_for_asin(asin, buybox_price, currency_code, True)
            fees_data = fees_response.payload
            if fees_data and fees_data.get('FeesEstimateResult'):
                fees_estimate = fees_data['FeesEstimateResult']['FeesEstimate']
                result_data['referralFee'] = fees_estimate.get('ReferralFee', {}).get('Amount', 0.0)
                result_data['fbaFee'] = fees_estimate.get('FbaFees', {}).get('Amount', 0.0)
            else:
                result_data['referralFee'] = 0.0
                result_data['fbaFee'] = 0.0
        else:
            result_data['referralFee'] = 0.0
            result_data['fbaFee'] = 0.0

        # 4. Currency Conversion
        logger.info("💱 Step 4: Converting currencies to USD...")
        result_data['buyboxPriceUSD'] = result_data['buyboxPrice']
        result_data['referralFeeUSD'] = result_data['referralFee']
        result_data['fbaFeeUSD'] = result_data['fbaFee']

        if currency_code and currency_code != 'USD':
            rates = get_exchange_rates(currency_code)
            if rates and 'USD' in rates:
                usd_rate = rates['USD']
                logger.info(f"Conversion rate from {currency_code} to USD: {usd_rate}")
                if result_data['buyboxPrice'] is not None:
                    result_data['buyboxPriceUSD'] = result_data['buyboxPrice'] * usd_rate
                if result_data['referralFee'] is not None:
                    result_data['referralFeeUSD'] = result_data['referralFee'] * usd_rate
                if result_data['fbaFee'] is not None:
                    result_data['fbaFeeUSD'] = result_data['fbaFee'] * usd_rate
            else:
                logger.error(f"Could not get USD conversion rate for {currency_code}")

        logger.info("✅ Product details fetched and processed successfully")
        return result_data

    except SellingApiException as e:
        error_message = str(e.payload if hasattr(e, 'payload') and e.payload else e)
        logger.error(f"❌ Amazon SP API Error: {error_message}")
        return {"error": f"API Error: {error_message}"}
    except Exception as e:
        logger.error(f"❌ Unexpected error: {str(e)}")
        logger.error(traceback.format_exc())
        return {"error": f"An unexpected server error occurred: {str(e)}"}

# --- API Endpoints ---
@app.route('/')
def health_check():
    """Health check endpoint"""
    na_status = "✅ Configured" if na_credentials and na_seller_id else "❌ Not configured"
    eu_status = "✅ Configured" if eu_credentials and eu_seller_id else "❌ Not configured"
    currency_status = "✅ Configured" if CURRENCY_API_KEY else "❌ Not configured"
    
    supported_marketplaces = list(MARKETPLACE_REGIONS.keys())
    
    return jsonify({
        "status": "healthy",
        "na_credentials": na_status,
        "eu_credentials": eu_status,
        "currency_api": currency_status,
        "supported_marketplaces": supported_marketplaces,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/get_product_details/<string:asin>', methods=['GET'])
def api_get_product_details(asin):
    """Get product details for a specific ASIN"""
    marketplace = request.args.get('marketplace', 'US')
    
    if marketplace not in MARKETPLACE_REGIONS:
        return jsonify({"error": f"Unsupported marketplace: {marketplace}"}), 400
    
    try:
        result = get_full_product_details_as_json(asin, marketplace)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in API endpoint: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/convert_currency', methods=['POST'])
def api_convert_currency():
    """Convert currency using current exchange rates"""
    try:
        data = request.get_json()
        amount = float(data.get('amount', 0))
        from_currency = data.get('from_currency', 'USD')
        to_currency = data.get('to_currency', 'USD')
        
        converted_amount = convert_currency(amount, from_currency, to_currency)
        
        if converted_amount is None:
            return jsonify({"error": "Currency conversion failed due to missing or invalid exchange rates."}), 500

        return jsonify({
            "success": True,
            "original_amount": amount,
            "original_currency": from_currency,
            "converted_amount": converted_amount,
            "target_currency": to_currency
        })
    except Exception as e:
        logger.error(f"Currency conversion error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Unhandled exception: {str(e)}")
    logger.error(traceback.format_exc())
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)