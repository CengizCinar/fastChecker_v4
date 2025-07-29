import os
import json
import logging
import traceback
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS
from sp_api.api import CatalogItems, ListingsRestrictions, Products, ProductFees
from sp_api.base import SellingApiException
from sp_api.base.marketplaces import Marketplaces
import requests

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
        logger.warning("CURRENCY_API_KEY not configured, using default rates")
        return {
            'USD': 1.0,
            'EUR': 0.85,
            'GBP': 0.73,
            'CAD': 1.25,
            'TRY': 30.0
        }
    
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
        logger.warning("No exchange rates available, using 1:1 conversion")
        return amount
    
    # Convert to USD first, then to target currency
    try:
        if from_currency == 'USD':
            usd_amount = amount
        else:
            from_rate = rates.get(from_currency, 1)
            usd_amount = amount / from_rate
        
        if to_currency == 'USD':
            return usd_amount
        else:
            to_rate = rates.get(to_currency, 1)
            return usd_amount * to_rate
    except Exception as e:
        logger.error(f"Currency conversion error: {e}")
        return amount

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
            logger.error(f"❌ Error fetching offers: {str(e)}")
            logger.error(traceback.format_exc())
            result_data['offers'] = []
            result_data['buyboxPrice'] = None
            result_data['currencyCode'] = None

        # 6. Fees
        logger.info("💸 Step 6: Calculating fees...")
        try:
            if buybox_price and currency_code:
                fees_response = fees_api.get_product_fees_estimate(
                    asin=asin,
                    price=float(buybox_price),
                    currency=currency_code,
                    marketplaceId=marketplace.marketplace_id,
                    isAmazonFulfilled=True
                )
                
                fees_data = fees_response.payload.get('FeesEstimate', {})
                fee_details = fees_data.get('FeeDetailList', [])
                
                referral_fee = 0
                fba_fee = 0
                
                for fee in fee_details:
                    fee_type = fee.get('FeeType', '')
                    fee_amount = fee.get('FinalFee', {}).get('Amount', 0)
                    
                    if fee_type == 'ReferralFee':
                        referral_fee = fee_amount
                    elif fee_type == 'FBAFees':
                        fba_fee = fee_amount
                
                result_data['referralFee'] = referral_fee
                result_data['fbaFee'] = fba_fee
                logger.info(f"✅ Fees calculated - Referral: {referral_fee}, FBA: {fba_fee}")
            else:
                result_data['referralFee'] = 0
                result_data['fbaFee'] = 0
                logger.warning("⚠️ Could not calculate fees - no buybox price")
                
        except Exception as e:
            logger.error(f"❌ Error calculating fees: {str(e)}")
            result_data['referralFee'] = 0
            result_data['fbaFee'] = 0

        # 7. BSR Data (if available)
        logger.info("📊 Step 7: Processing BSR data...")
        try:
            # This would be populated from external BSR data source
            # For now, we'll leave it empty
            result_data['bsr_data'] = {}
            logger.info("ℹ️ BSR data not implemented yet")
        except Exception as e:
            logger.warning(f"⚠️ BSR data processing error: {str(e)}")
            result_data['bsr_data'] = {}

        logger.info("✅ Product details processing completed successfully")
        return result_data

    except Exception as e:
        logger.error(f"❌ FATAL ERROR in get_full_product_details_as_json: {str(e)}")
        logger.error(traceback.format_exc())
        return {"error": f"Internal server error: {str(e)}"}

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