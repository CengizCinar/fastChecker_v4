// SP API Helper for FastChecker Chrome Extension

class SPAPIHelper {
    constructor() {
        this.marketplaces = {
            'US': { endpoint: 'https://sellingpartnerapi-na.amazon.com', marketplaceId: 'ATVPDKIKX0DER', region: 'us-east-1' },
            'CA': { endpoint: 'https://sellingpartnerapi-na.amazon.com', marketplaceId: 'A2EUQ1WTGCTBG2', region: 'us-east-1' },
            'MX': { endpoint: 'https://sellingpartnerapi-na.amazon.com', marketplaceId: 'A1AM78C64UM0Y8', region: 'us-east-1' },
            'BR': { endpoint: 'https://sellingpartnerapi-na.amazon.com', marketplaceId: 'A2Q3Y263D00KWC', region: 'us-east-1' },
            'DE': { endpoint: 'https://sellingpartnerapi-eu.amazon.com', marketplaceId: 'A1PA6795UKMFR9', region: 'eu-west-1' },
            'ES': { endpoint: 'https://sellingpartnerapi-eu.amazon.com', marketplaceId: 'A1RKKUPIHCS9HS', region: 'eu-west-1' },
            'FR': { endpoint: 'https://sellingpartnerapi-eu.amazon.com', marketplaceId: 'A13V1IB3VIYZZH', region: 'eu-west-1' },
            'IT': { endpoint: 'https://sellingpartnerapi-eu.amazon.com', marketplaceId: 'APJ6JRA9NG5V4', region: 'eu-west-1' },
            'NL': { endpoint: 'https://sellingpartnerapi-eu.amazon.com', marketplaceId: 'A1805IZSGTT6HS', region: 'eu-west-1' },
            'UK': { endpoint: 'https://sellingpartnerapi-eu.amazon.com', marketplaceId: 'A1F83G8C2ARO7P', region: 'eu-west-1' },
            'SE': { endpoint: 'https://sellingpartnerapi-eu.amazon.com', marketplaceId: 'A2NODRKZP88ZB9', region: 'eu-west-1' },
            'PL': { endpoint: 'https://sellingpartnerapi-eu.amazon.com', marketplaceId: 'A1C3SOZRARQ6R3', region: 'eu-west-1' },
            'EG': { endpoint: 'https://sellingpartnerapi-eu.amazon.com', marketplaceId: 'ARBP9OOSHTCHU', region: 'eu-west-1' },
            'TR': { endpoint: 'https://sellingpartnerapi-eu.amazon.com', marketplaceId: 'A33AVAJ2PDY3EV', region: 'eu-west-1' },
            'SA': { endpoint: 'https://sellingpartnerapi-eu.amazon.com', marketplaceId: 'A17E79C6D8DWNP', region: 'eu-west-1' },
            'AE': { endpoint: 'https://sellingpartnerapi-eu.amazon.com', marketplaceId: 'A2VIGQ35RCS4UG', region: 'eu-west-1' },
            'IN': { endpoint: 'https://sellingpartnerapi-eu.amazon.com', marketplaceId: 'A21TJRUUN4KGV', region: 'eu-west-1' },
            'JP': { endpoint: 'https://sellingpartnerapi-fe.amazon.com', marketplaceId: 'A1VC38T7YXB528', region: 'us-west-2' },
            'AU': { endpoint: 'https://sellingpartnerapi-fe.amazon.com', marketplaceId: 'A39IBJ37TRP1C6', region: 'us-west-2' },
            'SG': { endpoint: 'https://sellingpartnerapi-fe.amazon.com', marketplaceId: 'A19VAU5U5O7RUS', region: 'us-west-2' }
        };
        
        this.accessToken = null;
        this.tokenExpiry = null;
    }

    async getAccessToken(credentials) {
        if (this.accessToken && this.tokenExpiry && Date.now() < this.tokenExpiry) {
            return this.accessToken;
        }

        try {
            const response = await fetch('https://api.amazon.com/auth/o2/token', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: new URLSearchParams({
                    'grant_type': 'refresh_token',
                    'refresh_token': credentials.refresh_token,
                    'client_id': credentials.lwa_app_id,
                    'client_secret': credentials.lwa_client_secret
                })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(`Token request failed: ${errorData.error_description || response.statusText}`);
            }

            const data = await response.json();
            this.accessToken = data.access_token;
            this.tokenExpiry = Date.now() + (data.expires_in * 1000) - 60000;
            return this.accessToken;
        } catch (error) {
            console.error('Error getting access token:', error);
            throw error;
        }
    }

    async makeAPIRequest(endpoint, path, accessToken, method = 'GET', queryParams = {}) {
        const url = new URL(path, endpoint);
        Object.keys(queryParams).forEach(key => url.searchParams.append(key, queryParams[key]));

        const headers = {
            'x-amz-access-token': accessToken
        };

        try {
            const response = await fetch(url.toString(), { method, headers });
            
            if (!response.ok) {
                const errorData = await response.json();
                const errorMessage = errorData.errors?.[0]?.message || 'Unknown API Error';
                throw new Error(`API request failed: ${response.status} - ${errorMessage}`);
            }

            // Handle cases where response might be empty
            const text = await response.text();
            return text ? JSON.parse(text) : {};
        } catch (error) {
            console.error('API request error:', error);
            throw error;
        }
    }

    async getCatalogItem(asin, credentials, marketplace) {
        const accessToken = await this.getAccessToken(credentials);
        const marketplaceInfo = this.marketplaces[marketplace];
        if (!marketplaceInfo) throw new Error(`Unsupported marketplace: ${marketplace}`);

        const path = `/catalog/2022-04-01/items/${asin}`;
        const queryParams = {
            marketplaceIds: marketplaceInfo.marketplaceId,
            includedData: 'summaries'
        };
        
        return await this.makeAPIRequest(marketplaceInfo.endpoint, path, accessToken, 'GET', queryParams);
    }

    async getListingsRestrictions(asin, sellerId, credentials, marketplace) {
        const accessToken = await this.getAccessToken(credentials);
        const marketplaceInfo = this.marketplaces[marketplace];
        if (!marketplaceInfo) throw new Error(`Unsupported marketplace: ${marketplace}`);
        
        const path = '/listings/2021-08-01/restrictions';
        const queryParams = {
            asin: asin,
            sellerId: sellerId,
            marketplaceIds: marketplaceInfo.marketplaceId,
            conditionType: 'new_new'
        };

        return await this.makeAPIRequest(marketplaceInfo.endpoint, path, accessToken, 'GET', queryParams);
    }

    async checkASINSellability(asin, credentials, sellerId, marketplace) {
        try {
            // Get restrictions first, as it's the primary check
            const restrictionsResponse = await this.getListingsRestrictions(asin, sellerId, credentials, marketplace);
            const restrictions = restrictionsResponse.restrictions || [];

            // Get product information for context
            let productInfo = { brandName: 'N/A', itemName: 'N/A' };
            try {
                const catalogResponse = await this.getCatalogItem(asin, credentials, marketplace);
                const summary = catalogResponse.summaries?.[0];
                if (summary) {
                    productInfo = { brandName: summary.brand, itemName: summary.itemName };
                }
            } catch (error) {
                console.warn(`Could not get catalog info for ${asin}:`, error.message);
            }
            
            const isSellable = restrictions.length === 0;
            let message = isSellable ? 'Satılabilir' : 'Kısıtlama var';
            if (!isSellable) {
                message = restrictions[0]?.reasons?.[0]?.message || 'Onay gerekli.';
            }

            return {
                asin: asin,
                status: 'success',
                sellable: isSellable,
                message: message,
                details: {
                    brand: productInfo.brandName,
                    title: productInfo.itemName,
                    reasons: restrictions[0]?.reasons || []
                }
            };

        } catch (error) {
            console.error(`Error checking ASIN ${asin}:`, error);
            return {
                asin: asin,
                status: 'error',
                sellable: false,
                message: error.message,
                details: null
            };
        }
    }
}