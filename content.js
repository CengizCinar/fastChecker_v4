// content.js

// --- Global Değişkenler ---
let productData = {}; // Gelen ürün verisini globalde tutmak için
let calculatedCostPerItem = null;
let lowestEuPrice = null;

// --- Orijinal Fonksiyonlar ---
function getAsinFromUrl() {
    const match = window.location.pathname.match(/\/dp\/([A-Z0-9]{10})/);
    return match ? match[1] : null;
}

// --- GÜNCELLENMİŞ UI OLUŞTURMA FONKSİYONU ---
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
        <div id="fc-settings-view" class="fc-settings-view"></div>
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


// --- YENİ EKLENEN VE GÜNCELLENEN FONKSİYONLAR ---

// (YENİ GÖRÜNÜM) Ayarlar sayfasının HTML'ini oluşturur ve gösterir
function renderSettingsView(container) {
    const settingsView = container.querySelector('#fc-settings-view');
    chrome.storage.local.get(['shippingSettings'], (result) => {
        const settings = result.shippingSettings || {};
        // Varsayılan currency: USD
        const currency = settings.currency || 'USD';
        const currencySymbols = { USD: '$', EUR: '€', GBP: '£', TRY: '₺' };
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
        // Sadece rakam girişi için event
        settingsView.querySelectorAll('.fc-dimension-input').forEach(input => {
          input.addEventListener('input', function() {
            this.value = this.value.replace(/[^0-9]/g, '').slice(0, 4);
          });
        });
    });
}

// Girilen ayarları kaydeder
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

// Ana görünüm ve ayarlar görünümü arasında geçiş yapar
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

// (DÜZELTİLMİŞ) Ürün ve kargo verilerine göre hesaplama yapar
function calculateAndDisplayShipping() {
    chrome.storage.local.get(['shippingSettings'], (result) => {
        const settings = result.shippingSettings;
        const shippingDetailsEl = document.getElementById('fc-shipping-cost-details');
        if (!shippingDetailsEl) return;

        // Ayarlar veya ürün verisi eksikse hesaplama yapma
        if (!settings || !settings.pkgLength || !settings.pkgCost || (!productData.dimensions && !productData.package_dimensions) || (!productData.packageWeight && !product.package_weight)) {
            shippingDetailsEl.innerHTML = ''; return;
        }

        const pkgL = parseFloat(settings.pkgLength);
        const pkgW = parseFloat(settings.pkgWidth);
        const pkgH = parseFloat(settings.pkgHeight);
        const pkgMaxWeightKg = parseFloat(settings.pkgMaxWeight);
        const pkgCost = parseFloat(settings.pkgCost);

        let itemL, itemW, itemH, itemWeightGr;

        // **YENİ BİRİM KONTROL MANTIĞI**
        // Öncelik: Detaylı obje (package_dimensions)
        if (productData.package_dimensions && productData.package_dimensions.length && productData.package_dimensions.width && productData.package_dimensions.height) {
            const dims = productData.package_dimensions;
            const convertToCm = (dim) => {
                if (dim.unit && (dim.unit.toLowerCase() === 'inches' || dim.unit.toLowerCase() === 'inch')) {
                    return parseFloat(dim.value) * 2.54;
                }
                return parseFloat(dim.value); // Zaten cm veya birimsiz ise olduğu gibi al
            };
            itemL = convertToCm(dims.length);
            itemW = convertToCm(dims.width);
            itemH = convertToCm(dims.height);
        }
        // Geriye dönük uyumluluk: Eski string formatı
        else if (productData.dimensions) {
            const itemDimMatch = productData.dimensions.match(/(\d+\.?\d*)\s*x\s*(\d+\.?\d*)\s*x\s*(\d+\.?\d*)/);
            if(itemDimMatch) {
                itemL = parseFloat(itemDimMatch[1]);
                itemW = parseFloat(itemDimMatch[2]);
                itemH = parseFloat(itemDimMatch[3]);
            }
        }

        // Ağırlık için birim kontrolü
        if (productData.package_weight && productData.package_weight.value) {
            const weight = productData.package_weight;
            if (weight.unit && (weight.unit.toLowerCase() === 'pounds' || weight.unit.toLowerCase() === 'pound')) {
                itemWeightGr = parseFloat(weight.value) * 453.592;
            } else { // kilograms, grams, vs.
                // API'nin gram yolladığı varsayılıyor, değilse buraya ek case'ler eklenebilir
                itemWeightGr = parseFloat(weight.value);
            }
        }
        else if (productData.packageWeight) {
             const itemWeightMatch = productData.packageWeight.match(/(\d+\.?\d*)/);
             if(itemWeightMatch) itemWeightGr = parseFloat(itemWeightMatch[1]);
        }

        // Gerekli tüm değerler hesaplandı mı kontrol et
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

function updateCostInput() {
    if (calculatedCostPerItem !== null && lowestEuPrice !== null) {
        const costInput = document.getElementById('costInput');
        if (costInput) {
            const totalCost = (lowestEuPrice + calculatedCostPerItem) * 1.17;
            costInput.value = totalCost.toFixed(2);
            // Manuel olarak bir input olayı tetikle
            const event = new Event('input', { bubbles: true });
            costInput.dispatchEvent(event);
        }
    }
}


// --- Orijinal Fonksiyonlar ---
function formatCurrency(amount, currency) {
    if (typeof amount !== 'number' || isNaN(amount)) {
        return 'N/A';
    }
    if (typeof currency !== 'string' || currency.length < 3) {
        return amount.toFixed(2);
    }
    try {
        const options = { style: 'currency', currency: currency.toUpperCase() };
        const locales = { 'USD': 'en-US', 'CAD': 'en-CA', 'GBP': 'en-GB', 'EUR': 'de-DE', 'AUD': 'en-AU' };
        return amount.toLocaleString(locales[currency.toUpperCase()] || 'en-US', options);
    } catch (e) {
        console.error(`formatCurrency hatası: amount=${amount}, currency=${currency}`, e);
        return `${amount.toFixed(2)} ${currency}`;
    }
}

function truncateTitle(title, maxLength = 50) {
    if (!title || title.length <= maxLength) return title;
    return title.substr(0, title.lastIndexOf(' ', maxLength)) + '...';
}

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
        const priceCurrency = offer.ListingPrice?.CurrencyCode || defaultCurrency;
        const priceHtml = offer.IsBuyBoxWinner ? `<b>${formatCurrency(priceAmount, priceCurrency)}</b>` : formatCurrency(priceAmount, priceCurrency);
        return `
        <div class="fc-seller-row">
            <span class="fc-seller-ffm">${offer.IsFulfilledByAmazon ? 'FBA' : 'FBM'}</span>
            <a href="${sellerLink}" target="_blank" class="fc-seller-id">${sellerId}</a>
            <span class="fc-seller-price">${priceHtml}</span>
        </div>
    `}).join('');
    if (!sellersHtml) sellersHtml = '<div class="fc-no-seller">Aktif teklif yok.</div>';

    mainView.innerHTML = `
        <div class="fc-header"><span>✨ FastChecker AI Analysis</span><span class="fc-settings-icon">⚙️</span></div>
        <div class="fc-card fc-main-info">
             <div class="fc-main-info-3col">
                <div class="fc-main-col fc-main-img"><img class="fc-main-info-img" src="${data.imageUrl || ''}" alt="${data.title || ''}"></div>
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
            <div class="fc-input-row"><div class="input-group"><label for="costInput">Cost</label><input type="text" inputmode="decimal" pattern="[0-9]*" id="costInput" value="0" autocomplete="off" style="appearance: textfield;"></div><div class="input-group"><label for="saleInput">Sale</label><input type="text" inputmode="decimal" pattern="[0-9]*" id="saleInput" value="0" autocomplete="off" style="appearance: textfield;"></div></div>
            <div class="fc-result-row"><div class="result-item"><span>Profit</span><span id="profitResult" class="calculated-value">0.00</span></div><div class="result-item"><span>R.O.I</span><span id="roiResult" class="calculated-value">0.00%</span></div><div class="result-item"><span>Breakeven</span><span id="breakevenResult" class="calculated-value">0.00</span></div></div>
            <div class="fc-fee-details">
                <span id="referralFeeDisplay">Referral Fee: ${formatCurrency(data.referralFee, defaultCurrency)}</span>
                <span id="fbaFeeDisplay">FBA Fee: ${formatCurrency(data.fbaFee, defaultCurrency)}</span>
            </div>
            <div id="fc-shipping-cost-details" class="fc-fee-details"></div>
        </div>
        <div class="fc-card fc-sellers"><div class="fc-card-header"><span class="icon">📦</span><h4>Satıcılar (${offers.length})</h4></div><div class="fc-seller-list">${sellersHtml}</div></div>
        <div class="fc-card fc-eu-market-prices" id="fc-eu-market-prices">
            <div class="fc-card-header">
                <span class="icon">🇪🇺</span><h4>EU Market Fiyatları</h4>
            </div>
            <div class="fc-eu-prices-list" style="max-height: 120px; overflow-y: auto;">
                <div class="fc-no-eu-price">Fiyat verisi yok.</div>
            </div>
        </div>
    `;

    mainView.querySelector('.fc-settings-icon').addEventListener('click', () => toggleView(container));

    let bsrText = 'N/A', bsrNumber = null, categoryName = 'N/A';
    function formatBsr(num) {
        if (isNaN(num)) return 'N/A'; if (num < 1000) return num.toString(); return `${Math.floor(num / 1000)}k`;
    }
    function calculateBsrPercentage(bsr, category, bsrData) {
        if (!bsr || !category || !bsrData || !bsrData[category]) return ''; const categoryData = bsrData[category];
        const thresholds = {'0.5%': categoryData['Top 0.5% BSR'],'1%': categoryData['Top 1% BSR'],'2%': categoryData['Top 2% BSR'],'3%': categoryData['Top 3% BSR'],'5%': categoryData['Top 5% BSR'],'10%': categoryData['Top 10% BSR'],};
        if (bsr <= thresholds['0.5%']) return ' (0.5%)'; if (bsr <= thresholds['1%']) return ' (1%)'; if (bsr <= thresholds['2%']) return ' (2%)';
        if (bsr <= thresholds['3%']) return ' (3%)'; if (bsr <= thresholds['5%']) return ' (5%)'; if (bsr <= thresholds['10%']) return ' (10%)'; return '';
    }
    const thElements = Array.from(document.querySelectorAll('th'));
    const bsrTh = thElements.find(th => th.textContent.trim().includes('Best Sellers Rank') || th.textContent.trim().includes('Best-Sellers Rank'));
    if (bsrTh && bsrTh.nextElementSibling) { const bsrSpan = bsrTh.nextElementSibling.querySelector('span'); if (bsrSpan) bsrText = bsrSpan.textContent.trim(); }
    if (bsrText === 'N/A') {
        const detailBullets = document.getElementById('detailBullets_feature_div');
        if (detailBullets) { const bsrLi = Array.from(detailBullets.querySelectorAll('li')).find(li => li.innerText.includes('Best Sellers Rank')); if (bsrLi) bsrText = bsrLi.innerText.split(':')[1].trim(); }
    }
    if (bsrText === 'N/A') {
        const rankElement = Array.from(document.querySelectorAll('span.a-list-item')).find(el => el.textContent.includes('Best Sellers Rank'));
        if (rankElement) bsrText = rankElement.textContent.replace('Best Sellers Rank:', '').trim();
    }
    const bsrMatch = bsrText.match(/[\d,]+/); if (bsrMatch) bsrNumber = parseInt(bsrMatch[0].replace(/[#,]/g, ''), 10);
    const categoryMatch = bsrText.match(/in\s+([^\(]+)/); if (categoryMatch) categoryName = categoryMatch[1].trim();
    const bsrInput = mainView.querySelector('#bsrInput');
    if (bsrInput) { const percentageString = calculateBsrPercentage(bsrNumber, categoryName, data.bsr_data); bsrInput.value = `${formatBsr(bsrNumber)}${percentageString}`; }

    const costInput = mainView.querySelector('#costInput'); const saleInput = mainView.querySelector('#saleInput');
    const profitResult = mainView.querySelector('#profitResult'); const roiResult = mainView.querySelector('#roiResult'); const breakevenResult = mainView.querySelector('#breakevenResult');
    let referralFeePercentage = (data.buyboxPrice && data.referralFee) ? (data.referralFee / data.buyboxPrice) : 0;
    function formatInput(inputElement) { let value = inputElement.value; if (value && !value.includes('.')) inputElement.value = parseFloat(value).toFixed(2); }
    function calculateProfit() {
        const cost = parseFloat(costInput.value) || 0; const sale = parseFloat(saleInput.value) || 0;
        const currentReferralFee = sale * referralFeePercentage; const fbaFee = data.fbaFee || 0;
        const totalFees = currentReferralFee + fbaFee; const profit = sale - cost - totalFees;
        const roi = cost === 0 ? 0 : (profit / cost) * 100;
        let breakeven = (referralFeePercentage && referralFeePercentage < 1) ? (cost + fbaFee) / (1 - referralFeePercentage) : cost + fbaFee;
        profitResult.textContent = profit.toFixed(2); roiResult.textContent = `${roi.toFixed(2)}%`; breakevenResult.textContent = breakeven.toFixed(2);
        if (mainView.querySelector('#fbaFeeDisplay')) mainView.querySelector('#fbaFeeDisplay').textContent = `FBA Fee: ${formatCurrency(fbaFee, data.currencyCode)}`;
        if (mainView.querySelector('#referralFeeDisplay')) mainView.querySelector('#referralFeeDisplay').textContent = `Referral Fee: ${formatCurrency(currentReferralFee, data.currencyCode)}`;
        profitResult.classList.remove('positive', 'negative'); roiResult.classList.remove('positive', 'negative');
        if (profit > 0) profitResult.classList.add('positive'); else if (profit < 0) profitResult.classList.add('negative');
    }
    costInput.addEventListener('input', calculateProfit); costInput.addEventListener('blur', () => formatInput(costInput));
    saleInput.addEventListener('input', calculateProfit); saleInput.addEventListener('blur', () => formatInput(saleInput));
    if (data.buyboxPrice) saleInput.value = data.buyboxPrice.toFixed(2);
    calculateProfit();
    calculateAndDisplayShipping();
}

function renderEuMarketPrices(container, asin, prices) {
    const countryFlags = { 'DE': '🇩🇪', 'FR': '🇫🇷', 'IT': '🇮🇹', 'ES': '🇪🇸', 'UK': '🇬🇧', 'US': '🇺🇸', 'CA': '🇨🇦', 'MX': '🇲🇽', 'AU': '🇦🇺', 'JP': '🇯🇵', 'IN': '🇮🇳', 'BR': '🇧🇷', 'CN': '🇨🇳', 'AE': '🇦🇪', 'SA': '🇸🇦', 'SE': '🇸🇪', 'PL': '🇵🇱', 'EG': '🇪🇬', 'TR': '🇹🇷' };
    const marketDomains = { 'DE': 'de', 'FR': 'fr', 'IT': 'it', 'ES': 'es', 'UK': 'co.uk', 'US': 'com', 'CA': 'ca', 'MX': 'com.mx', 'AU': 'com.au', 'JP': 'co.jp', 'IN': 'in', 'BR': 'com.br', 'CN': 'cn', 'AE': 'ae', 'SA': 'sa', 'SE': 'se', 'PL': 'pl', 'EG': 'eg', 'TR': 'com.tr' };
    let euBox = container.querySelector('#fc-eu-market-prices'); if (!euBox) return;
    const list = euBox.querySelector('.fc-eu-prices-list'); if (!list) return;
    if (!prices || prices.length === 0) { list.innerHTML = '<div class="fc-no-eu-price">Fiyat verisi yok.</div>'; return; }
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

chrome.runtime && chrome.runtime.onMessage && chrome.runtime.onMessage.addListener((msg) => {
    if (msg.action === 'euMarketPrices' && msg.asin) {
        let container = document.getElementById('fastchecker-product-ui');
        if (!container) container = createUIContainer();
        renderEuMarketPrices(container, msg.asin, msg.prices);
    }
});

(function() {
    const asin = getAsinFromUrl();
    if (!asin) return;

    const marketPlaceMap = {
        'www.amazon.com': 'US',
        'www.amazon.ca': 'CA',
        'www.amazon.com.mx': 'MX',
        'www.amazon.com.br': 'BR',
        'www.amazon.co.uk': 'UK',
        'www.amazon.de': 'DE',
        'www.amazon.fr': 'FR',
        'www.amazon.it': 'IT',
        'www.amazon.es': 'ES',
        'www.amazon.com.au': 'AU',
        'www.amazon.co.jp': 'JP',
        'www.amazon.in': 'IN',
        'www.amazon.cn': 'CN',
        'www.amazon.com.tr': 'TR',
        'www.amazon.ae': 'AE',
        'www.amazon.sa': 'SA',
        'www.amazon.se': 'SE',
        'www.amazon.pl': 'PL',
        'www.amazon.eg': 'EG'
    };
    const currentMarketplace = marketPlaceMap[window.location.hostname];

    const container = createUIContainer();
    if (!container) return;
    fetch(`https://web-production-e38b7.up.railway.app/get_product_details/${asin}?marketplace=${currentMarketplace}`)
        .then(r => r.json())
        .then(data => {
            if (data.error) { updateUI(container, {}, data.error); }
            else { updateUI(container, data); }
        })
        .catch(e => updateUI(container, {}, e.message));
    renderEuMarketPrices(container, asin, []);
    chrome.runtime && chrome.runtime.sendMessage && chrome.runtime.sendMessage({
        action: 'fetchEuMarketPrices',
        asin: asin,
        markets: ['DE', 'FR', 'IT', 'ES']
    }, (resp) => {
        if (resp && !resp.success) {
            console.warn('EU market fiyat isteği başarısız:', resp.error);
        }
    });
})();