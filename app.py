import os
import json
from flask import Flask, jsonify, request
from flask_cors import CORS
from sp_api.api import CatalogItems, ListingsRestrictions, Products, ProductFees
from sp_api.base import Marketplaces, SellingApiException
from bsr_scraper import scrape_bsr_table_by_country

# --- Flask App Initialization ---
app = Flask(__name__)
CORS(app)

# --- Load BSR Data ---
print("Loading BSR tables from SellerAmp...")
BSR_TABLES = {
    'US': scrape_bsr_table_by_country(1),
    'CA': scrape_bsr_table_by_country(6),
}
print("BSR tables loaded.")

# --- Load Credentials from Environment Variables ---
# These are expected to be set in the Railway environment
try:
    credentials = {
        "refresh_token": os.environ['AMAZON_REFRESH_TOKEN'],
        "lwa_app_id": os.environ['AMAZON_LWA_APP_ID'],
        "lwa_client_secret": os.environ['AMAZON_LWA_CLIENT_SECRET'],
        # The role_arn is not strictly required for all calls but good practice
        # You might need to create an IAM role and provide its ARN here
        # "role_arn": os.environ.get('AMAZON_ROLE_ARN', 'arn:aws:iam::YOUR_AWS_ACCOUNT_ID:role/YourSPAPIRole')
    }
    SELLER_ID = os.environ['AMAZON_SELLER_ID']
    # Check if all essential credentials are present
    if not all(credentials.values()) or not SELLER_ID:
        raise KeyError("One or more environment variables are missing.")
except KeyError as e:
    print(f"FATAL ERROR: Environment variable not found - {e}")
    # Set a global error state
    credentials = None
    SELLER_ID = None

# --- Main Function to Get Product Details ---
def get_full_product_details_as_json(asin: str, marketplace_str: str):
    if not credentials or not SELLER_ID:
        return {"error": "Server is not configured. Missing credentials or Seller ID."}

    try:
        marketplace = getattr(Marketplaces, marketplace_str.upper())
    except AttributeError:
        return {"error": f"Invalid marketplace: '{marketplace_str}'."}

    try:
        # Initialize APIs
        catalog_api = CatalogItems(credentials=credentials, marketplace=marketplace)
        restrictions_api = ListingsRestrictions(credentials=credentials, marketplace=marketplace)
        products_api = Products(credentials=credentials, marketplace=marketplace)
        fees_api = ProductFees(credentials=credentials, marketplace=marketplace)

        result_data = {}

        # 1. Catalog Info
        catalog_response = catalog_api.get_catalog_item(asin, includedData=['summaries', 'identifiers', 'attributes', 'images'])
        payload = catalog_response.payload
        
        summary = payload.get('summaries', [{}])[0]
        result_data['asin'] = asin
        result_data['title'] = summary.get('itemName', 'N/A')
        result_data['brand'] = summary.get('brandName', 'N/A')
        
        # EAN
        identifiers = payload.get('identifiers', [{}])[0].get('identifiers', [])
        result_data['ean'] = next((i['identifier'] for i in identifiers if i.get('identifierType') == 'EAN'), 'N/A')

        # Image
        images = payload.get('images', [{}])[0].get('images', [])
        result_data['imageUrl'] = images[0].get('link') if images else None

        # Dimensions & Weight
        attributes = payload.get('attributes', {})
        package_dims = attributes.get('item_package_dimensions', [{}])[0]
        if package_dims and 'value' in package_dims.get('length', {}):
            length = package_dims['length']['value'] * 2.54
            width = package_dims['width']['value'] * 2.54
            height = package_dims['height']['value'] * 2.54
            result_data['dimensions'] = f"{length:.1f} x {width:.1f} x {height:.1f} cm"
        else:
            result_data['dimensions'] = "N/A"

        package_weight = attributes.get('item_package_weight', [{}])[0]
        if package_weight and 'value' in package_weight:
            weight_value = package_weight['value']
            weight_unit = package_weight.get('unit', '')
            if weight_unit.lower() in ['pounds', 'pound']:
                weight_kg = weight_value * 0.453592
                result_data['packageWeight'] = f"{(weight_kg * 1000):.0f} gr"
            else:
                result_data['packageWeight'] = f"{float(weight_value) * 1000:.0f} gr"
        else:
            result_data['packageWeight'] = "N/A"

        # 2. Restrictions
        restrictions_response = restrictions_api.get_listings_restrictions(asin=asin, sellerId=SELLER_ID, conditionType='new_new')
        restrictions = restrictions_response.payload.get('restrictions', [])
        result_data['isSellable'] = not bool(restrictions)
        result_data['restrictionReasons'] = [reason.get('message') for r in restrictions for reason in r.get('reasons', [])]

        # 3. Offers
        offers_response = products_api.get_item_offers(asin, "New", MarketplaceId=marketplace.marketplace_id)
        offers = offers_response.payload.get('Offers', [])
        active_offers = [o for o in offers if o.get('Quantity', 1) > 0 and o.get('IsFeatured', True)]
        result_data['offers'] = active_offers
        
        buybox_offer = next((o for o in active_offers if o.get('IsBuyBoxWinner')), None)
        buybox_price = float(buybox_offer['ListingPrice']['Amount']) if buybox_offer else None
        currency_code = buybox_offer['ListingPrice']['CurrencyCode'] if buybox_offer else None
        result_data['buyboxPrice'] = buybox_price
        result_data['currencyCode'] = currency_code

        # 4. Fees
        if buybox_price:
            fees_response = fees_api.get_product_fees_estimate([{'id_type': 'ASIN', 'id_value': asin, 'price': buybox_price, 'currency': currency_code, 'is_fba': True, 'marketplace_id': marketplace.marketplace_id}])
            fees_result = fees_response.payload[0]
            if fees_result.get('Status') == 'Success':
                estimate = fees_result['FeesEstimate']
                result_data['totalFees'] = estimate.get('TotalFeesEstimate', {}).get('Amount')
                result_data['referralFee'] = next((f['FeeAmount']['Amount'] for f in estimate.get('FeeDetailList', []) if f['FeeType'] == "ReferralFee"), 0.0)
                result_data['fbaFee'] = next((f['FeeAmount']['Amount'] for f in estimate.get('FeeDetailList', []) if f['FeeType'] == "FBAFees"), 0.0)
                result_data['netProfit'] = buybox_price - result_data.get('totalFees', 0.0)
            else:
                 result_data.update({'totalFees': None, 'referralFee': None, 'fbaFee': None, 'netProfit': None})
        else:
            result_data.update({'totalFees': None, 'referralFee': None, 'fbaFee': None, 'netProfit': None})

        return result_data

    except SellingApiException as e:
        error_message = str(e.payload or e)
        print(f"API Error: {error_message}")
        return {"error": f"API Error: {error_message}"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": f"An unexpected server error occurred: {str(e)}"}

# --- API Endpoints ---
@app.route('/')
def health_check():
    return jsonify({"status": "OK", "message": "FastChecker Backend is running!"})

@app.route('/get_product_details/<string:asin>', methods=['GET'])
def api_get_product_details(asin):
    if not credentials:
        return jsonify({"error": "Server is not configured correctly. Please check logs."}), 503

    marketplace = request.args.get('marketplace', 'US')
    data = get_full_product_details_as_json(asin, marketplace)
    
    if "error" in data:
        return jsonify(data), 500
    
    data['bsr_data'] = BSR_TABLES.get(marketplace.upper())
    return jsonify(data)

# --- Server Start ---
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5003))
    # Use 0.0.0.0 to be accessible from outside the container
    app.run(host='0.0.0.0', port=port, debug=False)
