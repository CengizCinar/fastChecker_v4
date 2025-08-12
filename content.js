// content.js

// --- Global Değişkenler ---
let productData = {}; // Gelen ürün verisini globalde tutmak için
let calculatedCostPerItem = null;
let lowestEuPrice = null;

// --- Temel Yardımcı Fonksiyonlar ---
function getAsinFromUrl() {
    const match = window.location.pathname.match(/\/dp\/([A-Z0-9]{10})/);
    return match ? match[1] : null;
}

function getMarketplaceFromUrl() {
    const hostname = window.location.hostname;
    const tldMap = {
        'amazon.com': 'US',
        'amazon.ca': 'CA',
        'amazon.com.mx': 'MX',
        'amazon.co.uk': 'GB',
        'amazon.de': 'DE',
        'amazon.fr': 'FR',
        'amazon.it': 'IT',
        'amazon.es': 'ES',
        'amazon.nl': 'NL',
        'amazon.se': 'SE',
        'amazon.pl': 'PL',
        'amazon.be': 'BE'
    };
    for (const domain in tldMap) {
        if (hostname.endsWith(domain)) {
            return tldMap[domain];
        }
    }
    return 'US'; // Varsayılan
}

// --- UI OLUŞTURMA ---
function createUIContainer() {
    const existingUI = document.getElementById('fastchecker-product-ui');
    if (existingUI) {
        existingUI.remove();
    }
    const container = document.createElement('div');
    container.id = 'fastchecker-product-ui';
    container.innerHTML = `
        <div id="fc-main-view">
            <div class="fc-loading">✨ FastChecker AI verileri analiz ediyor...</div>
        </div>
        <div id="fc-settings-view" class="fc-settings-view" style="display:none;"></div>
    `;
    const rightCol = document.getElementById('rightCol');
    if (rightCol) {
        rightCol.style.position = 'relative';
        rightCol.prepend(container);
    } else {
        console.error('FastChecker: Konumlandırma için #rightCol bulunamadı.');
        return null;
    }
    return container;
}

// --- AYARLAR GÖRÜNÜMÜ ---
function renderSettingsView(container) {
    const settingsView = container.querySelector('#fc-settings-view');
    chrome.storage.local.get(['shippingSettings'], (result) => {
        const settings = result.shippingSettings || {};
        const currency = settings.currency || 'USD';
        settingsView.innerHTML = `
            <div class="fc-card">
                <div class="fc-header">
                    <span>⚙️ Kargo Ayarları</span>
                    <span class="fc-settings-icon" id="fc-back-to-main">🏠</span>
                </div>
                <div class="fc-settings-body">
                    <div class="input-group">
                        <label>E x B x Y (cm)</label>
                        <div class="dimension-inputs">
                            <input type="text" maxlength="4" pattern="[0-9]*" inputmode="numeric" class="fc-dimension-input" id="pkgLength" placeholder="E" value="${settings.pkgLength || ''}">
                            <span>x</span>
                            <input type="text" maxlength="4" pattern="[0-9]*" inputmode="numeric" class="fc-dimension-input" id="pkgWidth" placeholder="B" value="${settings.pkgWidth || ''}">
                            <span>x</span>
                            <input type="text" maxlength="4" pattern="[0-9]*" inputmode="numeric" class="fc-dimension-input" id="pkgHeight" placeholder="Y" value="${settings.pkgHeight || ''}">
                        </div>
                    </div>
                    <div class="input-group">
                        <label for="pkgMaxWeight">Max. Koli Ağırlığı (kg)</label>
                        <input type="text" maxlength="4" pattern="[0-9]*" inputmode="numeric" class="fc-dimension-input" id="pkgMaxWeight" value="${settings.pkgMaxWeight || ''}">
                    </div>
                    <div class="input-group">
                        <label for="pkgCost">Koli Başı Kargo Ücreti</label>
                        <div style="display: flex; align-items: center; gap: 4px;">
                            <input type="text" maxlength="4" pattern="[0-9]*" inputmode="numeric" class="fc-dimension-input" id="pkgCost" value="${settings.pkgCost || ''}">
                            <select id="pkgCurrency" class="fc-currency-select">
                                <option value="USD" ${currency === 'USD' ? 'selected' : ''}>$</option>
                                <option value="EUR" ${currency === 'EUR' ? 'selected' : ''}>€</option>
                                <option value="GBP" ${currency === 'GBP' ? 'selected' : ''}>£</option>
                                <option value="TRY" ${currency === 'TRY' ? 'selected' : ''}>₺</option>
                            </select>
                        </div>
                    </div>
                    <button id="saveSettingsBtn" class="fc-settings-btn">Ayarları Kaydet</button>
                </div>
            </div>
        `;
        settingsView.querySelector('#saveSettingsBtn').addEventListener('click', saveShippingSettings);
        settingsView.querySelector('#fc-back-to-main').addEventListener('click', () => toggleView(container));
        settingsView.querySelectorAll('.fc-dimension-input').forEach(input => {
            input.addEventListener('input', function() {
                this.value = this.value.replace(/[^0-9]/g, '').slice(0, 4);
            });
        });
    });
}

function saveShippingSettings() {
    const settings = {
        pkgLength: document.getElementById('pkgLength').value,
        pkgWidth: document.getElementById('pkgWidth').value,
        pkgHeight: document.getElementById('pkgHeight').value,
        pkgMaxWeight: document.getElementById('pkgMaxWeight').value,
        pkgCost: document.getElementById('pkgCost').value,
        currency: document.getElementById('pkgCurrency') ? document.getElementById('pkgCurrency').value : 'USD',
    };
    chrome.storage.local.set({ shippingSettings: settings }, () => {
        console.log('FastChecker: Kargo ayarları kaydedildi.');
        alert('Ayarlar kaydedildi!');
        calculateAndDisplayShipping();
    });
}

function toggleView(container) {
    const mainView = container.querySelector('#fc-main-view');
    const settingsView = container.querySelector('#fc-settings-view');
    if (mainView.style.display === 'none') {
        mainView.style.display = 'block';
        settingsView.style.display = 'none';
    } else {
        mainView.style.display = 'none';
        settingsView.style.display = 'block';
        renderSettingsView(container);
    }
}

// --- HESAPLAMA VE DÖNÜŞTÜRME FONKSİYONLARI ---
function calculateAndDisplayShipping() {
    chrome.storage.local.get(['shippingSettings'], (result) => {
        const settings = result.shippingSettings;
        const shippingDetailsEl = document.getElementById('fc-shipping-cost-details');
        if (!shippingDetailsEl) return;
        if (!settings || !settings.pkgLength || !settings.pkgCost || (!productData.dimensions && !productData.package_dimensions) || (!productData.packageWeight && !productData.package_weight)) {
            shippingDetailsEl.innerHTML = ''; return;
        }

        const pkgL = parseFloat(settings.pkgLength);
        const pkgW = parseFloat(settings.pkgWidth);
        const pkgH = parseFloat(settings.pkgHeight);
        const pkgMaxWeightKg = parseFloat(settings.pkgMaxWeight);
        const pkgCost = parseFloat(settings.pkgCost);
        let itemL, itemW, itemH, itemWeightGr;

        if (productData.package_dimensions && productData.package_dimensions.length && productData.package_dimensions.width && productData.package_dimensions.height) {
            const dims = productData.package_dimensions;
            const convertToCm = (dim) => {
                if (dim.unit && (dim.unit.toLowerCase() === 'inches' || dim.unit.toLowerCase() === 'inch')) {
                    return parseFloat(dim.value) * 2.54;
                }
                return parseFloat(dim.value);
            };
            itemL = convertToCm(dims.length);
            itemW = convertToCm(dims.width);
            itemH = convertToCm(dims.height);
        } else if (productData.dimensions) {
            const itemDimMatch = productData.dimensions.match(/(\d+\.?\d*)\s*x\s*(\d+\.?\d*)\s*x\s*(\d+\.?\d*)/);
            if(itemDimMatch) {
                itemL = parseFloat(itemDimMatch[1]);
                itemW = parseFloat(itemDimMatch[2]);
                itemH = parseFloat(itemDimMatch[3]);
            }
        }

        if (productData.package_weight && productData.package_weight.value) {
            const weight = productData.package_weight;
            if (weight.unit && (weight.unit.toLowerCase() === 'pounds' || weight.unit.toLowerCase() === 'pound')) {
                itemWeightGr = parseFloat(weight.value) * 453.592;
            } else {
                itemWeightGr = parseFloat(weight.value);
            }
        } else if (productData.packageWeight) {
             const itemWeightMatch = productData.packageWeight.match(/(\d+\.?\d*)/);
             if(itemWeightMatch) itemWeightGr = parseFloat(itemWeightMatch[1]);
        }

        if (!itemL || !itemW || !itemH || !itemWeightGr || !pkgL || !pkgW || !pkgH || !pkgMaxWeightKg || !pkgCost) {
            shippingDetailsEl.innerHTML = ''; return;
        }
        
        const itemDims = [itemL, itemW, itemH].sort((a, b) => a - b);
        const pkgDims = [pkgL, pkgW, pkgH].sort((a, b) => a - b);
        if (itemDims[0] > pkgDims[0] || itemDims[1] > pkgDims[1] || itemDims[2] > pkgDims[2]) {
             shippingDetailsEl.innerHTML = '<span class="negative">Ürün koliye fiziksel olarak sığmıyor.</span>';
             return;
        }

        const pkgMaxWeightGr = pkgMaxWeightKg * 1000;
        const itemVolume = itemL * itemW * itemH;
        const pkgVolume = pkgL * pkgW * pkgH;
        const fitByVol = itemVolume > 0 ? Math.floor(pkgVolume / itemVolume) : 0;
        const fitByWeight = itemWeightGr > 0 ? Math.floor(pkgMaxWeightGr / itemWeightGr) : 0;
        const itemsPerBox = Math.min(fitByVol, fitByWeight);
        const costPerItem = itemsPerBox > 0 ? pkgCost / itemsPerBox : 0;

        if (itemsPerBox > 0) {
            shippingDetailsEl.innerHTML = `Sığacak Adet: <b>${itemsPerBox}</b> | Adet Başı Kargo: <b>${formatCurrency(costPerItem, settings.currency)}</b>`;
            calculatedCostPerItem = costPerItem;
            updateCostInput();
        } else {
            shippingDetailsEl.innerHTML = '<span class="negative">Ürün koliye sığmıyor (Hacim/Ağırlık).</span>';
        }
    });
}

function convertCurrency(amount, from, to, rates) {
    if (!rates || typeof rates !== 'object' || from === to) return amount;
    const rateKey = `${from}_${to}`;
    const inverseRateKey = `${to}_${from}`;
    if (rates[rateKey]) return amount * rates[rateKey];
    if (rates[inverseRateKey]) return amount / rates[inverseRateKey];
    console.error(`FastChecker: Dönüşüm kuru bulunamadı: ${from} -> ${to}`);
    return null;
}

function updateCostInput() {
    if (calculatedCostPerItem === null || lowestEuPrice === null || !productData.exchangeRates || !productData.currencyCode) {
        return;
    }
    chrome.storage.local.get(['shippingSettings'], (result) => {
        const settings = result.shippingSettings;
        if (!settings || !settings.currency) return;

        const shippingCostCurrency = settings.currency;
        const targetCurrency = productData.currencyCode;
        const lowestEuPriceConverted = convertCurrency(lowestEuPrice, 'EUR', targetCurrency, productData.exchangeRates);
        const shippingCostConverted = convertCurrency(calculatedCostPerItem, shippingCostCurrency, targetCurrency, productData.exchangeRates);

        if (lowestEuPriceConverted === null || shippingCostConverted === null) return;

        const costInput = document.getElementById('costInput');
        if (costInput) {
            const totalCost = lowestEuPriceConverted + shippingCostConverted;
            costInput.value = totalCost.toFixed(2);
            costInput.dispatchEvent(new Event('input', { bubbles: true }));
        }
    });
}

function formatCurrency(amount, currency) {
    if (typeof amount !== 'number' || isNaN(amount)) return 'N/A';
    if (typeof currency !== 'string' || currency.length < 3) return amount.toFixed(2);
    try {
        const options = { style: 'currency', currency: currency.toUpperCase() };
        const locales = { 'USD': 'en-US', 'CAD': 'en-CA', 'GBP': 'en-GB', 'EUR': 'de-DE' };
        return amount.toLocaleString(locales[currency.toUpperCase()] || 'en-US', options);
    } catch (e) {
        return `${amount.toFixed(2)} ${currency}`;
    }
}



// --- ANA UI GÜNCELLEME ---
function updateUI(container, data, error = null) {
    const mainView = container.querySelector('#fc-main-view');

    if (error) {
        mainView.innerHTML = `<div class="fc-header"><span></span><span class="fc-settings-icon">⚙️</span></div><div class="fc-error">Hata: ${error}</div>`;
        mainView.querySelector('.fc-settings-icon').addEventListener('click', () => toggleView(container));
        return;
    }
    
    productData = data;
    const offers = (data.offers || []).filter(Boolean);
    const defaultCurrency = data.currencyCode || 'USD';
    const sellableStatus = data.isSellable ? '<span class="fc-status fc-sellable">SATILABİLİR</span>' : '<span class="fc-status fc-not-sellable">ONAY GEREKLİ</span>';
    
    let sellersHtml = offers.map(offer => {
        const sellerId = offer.SellerId || 'N/A';
        const sellerLink = `https://www.amazon.com/sp?ie=UTF8&seller=${sellerId}`;
        const priceAmount = offer.ListingPrice?.Amount;
        const priceHtml = offer.IsBuyBoxWinner ? `<b>${formatCurrency(priceAmount, defaultCurrency)}</b>` : formatCurrency(priceAmount, defaultCurrency);
        return `
        <div class="fc-seller-row">
            <span class="fc-seller-ffm">${offer.IsFulfilledByAmazon ? 'FBA' : 'FBM'}</span>
            <a href="${sellerLink}" target="_blank" class="fc-seller-id">${sellerId}</a>
            <span class="fc-seller-price">${priceHtml}</span>
        </div>
        `
    }).join('');
    if (!sellersHtml) sellersHtml = '<div class="fc-no-seller">Aktif teklif yok.</div>';

    mainView.innerHTML = `
        <div class="fc-header"><span>✨ FastChecker AI Analysis</span><span class="fc-settings-icon">⚙️</span></div>
        <div class="fc-card fc-main-info">
            <div class="fc-main-info-3col">
                <div class="fc-main-col fc-main-img"><img class="fc-main-info-img" src="${data.imageUrl || ''}" alt=""></div>
                <div class="fc-main-col fc-main-asin-ean">
                    <div class="fc-main-asin"><b>ASIN:</b> ${data.asin || 'N/A'}</div>
                    <div class="fc-main-ean"><b>EAN:</b> ${data.ean || 'N/A'}</div>
                </div>
                <div class="fc-main-col fc-main-brand">
                    <div class="fc-main-brand-label"><b>Marka:</b></div>
                    <div class="fc-main-brand-name">${data.brand || 'N/A'}</div>
                </div>
            </div>
            <div class="fc-main-info-row">
                <div class="fc-main-dim"><b>Boyut:</b> ${data.dimensions || 'N/A'}</div>
                <div class="fc-main-weight"><b>Ağırlık:</b> ${data.packageWeight || 'N/A'}</div>
            </div>
            <div class="fc-main-restriction">${sellableStatus}</div>
        </div>
        <div class="fc-card fc-finance-calculator">
            <div class="fc-card-header"><span>Profit Calculator</span></div>
            <div class="fc-input-row"><div class="input-group"><label for="bsrInput">BSR</label><input type="text" id="bsrInput" value="N/A" readonly></div><div class="input-group"><label for="estimatedSalesInput">Estimated Sales</label><input type="text" id="estimatedSalesInput" value="N/A" readonly></div></div>
            <div class="fc-input-row"><div class="input-group"><label for="costInput">Cost</label><input type="text" inputmode="decimal" id="costInput" value="0"></div><div class="input-group"><label for="saleInput">Sale</label><input type="text" inputmode="decimal" id="saleInput" value="0"></div></div>
            <div class="fc-result-row"><div class="result-item"><span>Profit</span><span id="profitResult" class="calculated-value">0.00</span></div><div class="result-item"><span>R.O.I</span><span id="roiResult" class="calculated-value">0.00%</span></div><div class="result-item"><span>Breakeven</span><span id="breakevenResult" class="calculated-value">0.00</span></div></div>
            <div class="fc-fee-details">
                <span id="referralFeeDisplay">Referral Fee: ${formatCurrency(data.referralFee, defaultCurrency)}</span>
                <span id="fbaFeeDisplay">FBA Fee: ${formatCurrency(data.fbaFee, defaultCurrency)}</span>
            </div>
            <div id="fc-shipping-cost-details" class="fc-fee-details"></div>
        </div>
        <div class="fc-card fc-sellers"><div class="fc-card-header"><h4>Satıcılar (${offers.length})</h4></div><div class="fc-seller-list">${sellersHtml}</div></div>
        <div class="fc-card fc-eu-market-prices" id="fc-eu-market-prices">
            <div class="fc-card-header"><h4>🇪🇺 EU Market Fiyatları</h4></div>
            <div class="fc-eu-prices-list"><div class="fc-no-eu-price">Fiyat verisi yok.</div></div>
        </div>
    `;

    mainView.querySelector('.fc-settings-icon').addEventListener('click', () => toggleView(container));
    
    // --- YENİ VE BASİT BSR MANTIĞI ---
    // Veriyi doğrudan backend'den al, frontend'de işlem yapma.
    const bsrInput = mainView.querySelector('#bsrInput');
    if (bsrInput && data.bsr_analysis && data.bsr_analysis.enhanced_display) {
        bsrInput.value = data.bsr_analysis.enhanced_display;
    } else if (bsrInput) {
        bsrInput.value = 'N/A';
    }
    // --- BSR MANTIĞI SONU ---

    // Hesaplayıcıyı kur
    const costInput = mainView.querySelector('#costInput');
    const saleInput = mainView.querySelector('#saleInput');
    const profitResult = mainView.querySelector('#profitResult');
    const roiResult = mainView.querySelector('#roiResult');
    const breakevenResult = mainView.querySelector('#breakevenResult');
    let referralFeePercentage = (data.buyboxPrice && data.referralFee) ? (data.referralFee / data.buyboxPrice) : 0;

    function calculateProfit() {
        const cost = parseFloat(costInput.value) || 0;
        const sale = parseFloat(saleInput.value) || 0;
        const currentReferralFee = sale * referralFeePercentage;
        const fbaFee = data.fbaFee || 0;
        const totalFees = currentReferralFee + fbaFee;
        const profit = sale - cost - totalFees;
        const roi = cost === 0 ? 0 : (profit / cost) * 100;
        let breakeven = (referralFeePercentage < 1) ? (cost + fbaFee) / (1 - referralFeePercentage) : cost + fbaFee;
        
        profitResult.textContent = formatCurrency(profit, defaultCurrency);
        roiResult.textContent = `${roi.toFixed(2)}%`;
        breakevenResult.textContent = formatCurrency(breakeven, defaultCurrency);
        
        profitResult.classList.remove('positive', 'negative');
        if (profit > 0) profitResult.classList.add('positive');
        else if (profit < 0) profitResult.classList.add('negative');

        roiResult.classList.remove('positive', 'negative');
        if (roi > 0) roiResult.classList.add('positive');
        else if (roi < 0) roiResult.classList.add('negative');

        mainView.querySelector('#referralFeeDisplay').textContent = `Referral Fee: ${formatCurrency(currentReferralFee, defaultCurrency)}`;
    }

    costInput.addEventListener('input', calculateProfit);
    saleInput.addEventListener('input', calculateProfit);
    if (data.buyboxPrice) {
        saleInput.value = data.buyboxPrice.toFixed(2);
    }
    calculateProfit();
    calculateAndDisplayShipping();

    // ANA VERİ PAKETİ İÇİNDE GELEN EU FİYATLARINI EKRANA ÇİZ
    if (data.eu_business_prices) {
        renderEuMarketPrices(container, data.asin, data.eu_business_prices);
    }
}


function renderEuMarketPrices(container, asin, prices) {
    const countryFlags = { 'DE': '🇩🇪', 'FR': '🇫🇷', 'IT': '🇮🇹', 'ES': '🇪🇸', 'UK': '🇬🇧' };
    const marketDomains = { 'DE': 'de', 'FR': 'fr', 'IT': 'it', 'ES': 'es', 'UK': 'co.uk' };
    let euBox = container.querySelector('#fc-eu-market-prices');
    if (!euBox) return;
    const list = euBox.querySelector('.fc-eu-prices-list');
    if (!list || !prices || prices.length === 0) {
        list.innerHTML = '<div class="fc-no-eu-price">Fiyat verisi yok.</div>';
        return;
    }
    list.innerHTML = `
        <table class="fc-eu-market-table">
            <thead><tr><th>Ülke</th><th>Adet</th><th>Fiyat</th></tr></thead>
            <tbody>
                ${prices.map(p => `
                    <tr>
                        <td>${countryFlags[p.market] || ''} ${p.market}</td>
                        <td>${p.moq}</td>
                        <td><a href="https://www.amazon.${marketDomains[p.market] || 'com'}/dp/${asin}" target="_blank">${formatCurrency(p.price, p.currency || 'EUR')}</a></td>
                    </tr>
                `).join('')}
            </tbody>
        </table>`;

    const euroPrices = prices.filter(p => p.currency === 'EUR');
    if (euroPrices.length > 0) {
        lowestEuPrice = Math.min(...euroPrices.map(p => p.price));
        updateCostInput();
    }
}

(function() {
    const asin = getAsinFromUrl();
    if (!asin) return;

    const container = createUIContainer();
    if (!container) return;

    // Sadece tek bir istek gönderiyoruz
    chrome.runtime.sendMessage({
        action: 'fetchProductDetails',
        asin: asin,
        marketplace: getMarketplaceFromUrl()
    });

    // Gelen tek mesaja göre UI'ı çiziyoruz
    chrome.runtime.onMessage.addListener(function messageListener(request, sender, sendResponse) {
        if (request.asin !== asin || request.action !== "displayProductDetails") return;

        if (request.data.error) {
            updateUI(container, null, request.data.error);
        } else {
            updateUI(container, request.data);
        }
    });
})();
