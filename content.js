// content.js
function getAsinFromUrl() {
    const match = window.location.pathname.match(/\/dp\/([A-Z0-9]{10})/);
    return match ? match[1] : null;
}

function createUIContainer() {
    const existingUI = document.getElementById('fastchecker-product-ui');
    if (existingUI) {
        existingUI.remove();
    }

    const container = document.createElement('div');
    container.id = 'fastchecker-product-ui';
    container.innerHTML = `<div class="fc-loading">✨ FastChecker AI verileri analiz ediyor...</div>`;

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

// --- GÜÇLENDİRİLMİŞ formatCurrency ---
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

// --- GÜÇLENDİRİLMİŞ updateUI ---
function updateUI(container, data, error = null) {
    if (error) {
        container.innerHTML = `<div class="fc-header"><span></span><span class="fc-close">&times;</span></div><div class="fc-error">Hata: ${error}</div>`;
        container.querySelector('.fc-close').addEventListener('click', () => container.remove());
        return;
    }

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

    container.innerHTML = `
        <div class="fc-header"><span>✨ FastChecker AI Analysis</span><span class="fc-close">&times;</span></div>
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
                <div class="fc-main-dim"><b>Boyutlar:</b> ${data.dimensions || 'N/A'}</div>
                <div class="fc-main-weight"><b>Ağırlık:</b> ${data.packageWeight || 'N/A'}</div>
            </div>
            <div class="fc-main-restriction">${sellableStatus}</div>
        </div>
        <div class="fc-card fc-finance-calculator"> 
            <div class="fc-card-header"><span>Profit Calculator</span></div>
            <div class="fc-input-row"><div class="input-group"><label for="bsrInput">BSR</label><input type="text" id="bsrInput" value="N/A" readonly></div><div class="input-group"><label for="estimatedSalesInput">Estimated Sales</label><input type="text" id="estimatedSalesInput" value="N/A" readonly></div></div>
            <div class="fc-input-row"><div class="input-group"><label for="costInput">Cost</label><input type="text" inputmode="decimal" pattern="[0-9]*" id="costInput" value="0" autocomplete="off" style="appearance: textfield;"></div><div class="input-group"><label for="saleInput">Sale</label><input type="text" inputmode="decimal" pattern="[0-9]*" id="saleInput" value="0" autocomplete="off" style="appearance: textfield;"></div></div>
            <div class="fc-result-row"><div class="result-item"><span>Profit</span><span id="profitResult" class="calculated-value">0.00</span></div><div class="result-item"><span>R.O.I</span><span id="roiResult" class="calculated-value">0.00%</span></div><div class="result-item"><span>Breakeven</span><span id="breakevenResult" class="calculated-value">0.00</span></div></div>
            <div class="fc-fee-details"><span id="referralFeeDisplay">Referral Fee: ${formatCurrency(data.referralFee, defaultCurrency)}</span><span id="fbaFeeDisplay">FBA Fee: ${formatCurrency(data.fbaFee, defaultCurrency)}</span></div>
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

    container.querySelector('.fc-close').addEventListener('click', () => container.remove());

    // --- START of BSR scraping and formatting logic ---
    let bsrText = 'N/A';
    let bsrNumber = null;
    let categoryName = 'N/A';

    // Function to format BSR number
    function formatBsr(num) {
        if (isNaN(num)) return 'N/A';
        if (num < 1000) return num.toString();
        return `${Math.floor(num / 1000)}k`;
    }

    // Function to calculate BSR percentage
    function calculateBsrPercentage(bsr, category, bsrData) {
        if (!bsr || !category || !bsrData || !bsrData[category]) {
            return ''; // Return empty string if data is missing
        }
        const categoryData = bsrData[category];
        const thresholds = {
            '0.5%': categoryData['Top 0.5% BSR'],
            '1%': categoryData['Top 1% BSR'],
            '2%': categoryData['Top 2% BSR'],
            '3%': categoryData['Top 3% BSR'],
            '5%': categoryData['Top 5% BSR'],
            '10%': categoryData['Top 10% BSR'],
        };

        if (bsr <= thresholds['0.5%']) return ' (0.5%)';
        if (bsr <= thresholds['1%']) return ' (1%)';
        if (bsr <= thresholds['2%']) return ' (2%)';
        if (bsr <= thresholds['3%']) return ' (3%)';
        if (bsr <= thresholds['5%']) return ' (5%)';
        if (bsr <= thresholds['10%']) return ' (10%)';

        return ''; // Return empty if not in top 10%
    }

    // Strategy 1: Find by table header
    const thElements = Array.from(document.querySelectorAll('th'));
    const bsrTh = thElements.find(th => th.textContent.trim().includes('Best Sellers Rank') || th.textContent.trim().includes('Best-Sellers Rank'));
    if (bsrTh) {
        const bsrTd = bsrTh.nextElementSibling;
        if (bsrTd) {
            const bsrSpan = bsrTd.querySelector('span');
            if (bsrSpan) {
                bsrText = bsrSpan.textContent.trim();
            }
        }
    }

    // Strategy 2: Find in detail bullets list if first one failed
    if (bsrText === 'N/A') {
        const detailBullets = document.getElementById('detailBullets_feature_div');
        if (detailBullets) {
            const bsrLi = Array.from(detailBullets.querySelectorAll('li')).find(li => li.innerText.includes('Best Sellers Rank'));
            if (bsrLi) {
                bsrText = bsrLi.innerText.split(':')[1].trim();
            }
        }
    }
    
    // Strategy 3: Generic search for a list item span
    if (bsrText === 'N/A') {
        const rankElement = Array.from(document.querySelectorAll('span.a-list-item'))
            .find(el => el.textContent.includes('Best Sellers Rank'));
        if (rankElement) {
            bsrText = rankElement.textContent.replace('Best Sellers Rank:', '').trim();
        }
    }

    // Extract the number and category from the BSR string
    const bsrMatch = bsrText.match(/[\d,]+/);
    if (bsrMatch) {
        bsrNumber = parseInt(bsrMatch[0].replace(/[#,]/g, ''), 10);
    }
    const categoryMatch = bsrText.match(/in\s+([^\(]+)/);
    if (categoryMatch) {
        categoryName = categoryMatch[1].trim();
    }

    const bsrInput = container.querySelector('#bsrInput');
    if (bsrInput) {
        const percentageString = calculateBsrPercentage(bsrNumber, categoryName, data.bsr_data);
        bsrInput.value = `${formatBsr(bsrNumber)}${percentageString}`;
    }
    // --- END of BSR scraping and formatting logic ---

    // Profit Calculator Logic
    const costInput = container.querySelector('#costInput');
    const saleInput = container.querySelector('#saleInput');
    const profitResult = container.querySelector('#profitResult');
    const roiResult = container.querySelector('#roiResult');
    const breakevenResult = container.querySelector('#breakevenResult');

    let referralFeePercentage = 0;
    if (data.buyboxPrice && data.referralFee) {
        referralFeePercentage = (data.referralFee / data.buyboxPrice);
    }

    function formatInput(inputElement) {
        let value = inputElement.value;
        if (value && !value.includes('.')) {
            inputElement.value = parseFloat(value).toFixed(2);
        }
    }

    function calculateProfit() {
        const cost = parseFloat(costInput.value) || 0;
        const sale = parseFloat(saleInput.value) || 0;
        const currentReferralFee = sale * referralFeePercentage;
        const fbaFee = data.fbaFee || 0;
        const totalFees = currentReferralFee + fbaFee;
        const profit = sale - cost - totalFees;
        const roi = cost === 0 ? 0 : (profit / cost) * 100;
        // Doğru breakeven hesabı: (cost + fbaFee) / (1 - referralFeePercentage)
        let breakeven = 0;
        if (referralFeePercentage && referralFeePercentage < 1) {
            breakeven = (cost + fbaFee) / (1 - referralFeePercentage);
        } else {
            breakeven = cost + fbaFee;
        }
        profitResult.textContent = profit.toFixed(2);
        roiResult.textContent = `${roi.toFixed(2)}%`;
        breakevenResult.textContent = breakeven.toFixed(2);
        const fbaFeeDisplay = container.querySelector('#fbaFeeDisplay');
        if (fbaFeeDisplay) {
            fbaFeeDisplay.textContent = `FBA Fee: ${formatCurrency(fbaFee, data.currencyCode)}`;
        }
        const referralFeeDisplay = container.querySelector('#referralFeeDisplay');
        if (referralFeeDisplay) {
            referralFeeDisplay.textContent = `Referral Fee: ${formatCurrency(currentReferralFee, data.currencyCode)}`;
        }
        profitResult.classList.remove('positive', 'negative');
        roiResult.classList.remove('positive', 'negative');
        if (profit > 0) {
            profitResult.classList.add('positive');
        } else if (profit < 0) {
            profitResult.classList.add('negative');
        }
        if (roi > 0) {
            roiResult.classList.add('positive');
        } else if (roi < 0) {
            roiResult.classList.add('negative');
        }
    }

    costInput.addEventListener('input', calculateProfit);
    costInput.addEventListener('blur', () => formatInput(costInput));
    saleInput.addEventListener('input', calculateProfit);
    saleInput.addEventListener('blur', () => formatInput(saleInput));
    if (data.buyboxPrice) {
        saleInput.value = data.buyboxPrice.toFixed(2);
    }
    calculateProfit();
}

// --- EU MARKET FİYATLARI ALANI EKLEME ---
function renderEuMarketPrices(container, asin, prices) {
    const countryFlags = {
        'DE': '🇩🇪', 'FR': '🇫🇷', 'IT': '🇮🇹', 'ES': '🇪🇸', 'NL': '🇳🇱',
        'UK': '🇬🇧', 'US': '🇺🇸', 'CA': '🇨🇦', 'MX': '🇲🇽', 'AU': '🇦🇺',
        'JP': '🇯🇵', 'IN': '🇮🇳', 'BR': '🇧🇷', 'CN': '🇨🇳', 'AE': '🇦🇪',
        'SA': '🇸🇦', 'SE': '🇸🇪', 'PL': '🇵🇱', 'EG': '🇪🇬', 'TR': '🇹🇷'
    };
    const marketDomains = {
        'DE': 'de', 'FR': 'fr', 'IT': 'it', 'ES': 'es', 'NL': 'nl',
        'UK': 'co.uk', 'US': 'com', 'CA': 'ca', 'MX': 'com.mx', 'AU': 'com.au',
        'JP': 'co.jp', 'IN': 'in', 'BR': 'com.br', 'CN': 'cn', 'AE': 'ae',
        'SA': 'sa', 'SE': 'se', 'PL': 'pl', 'EG': 'eg', 'TR': 'com.tr'
    };

    let euBox = container.querySelector('#fc-eu-market-prices');
    if (!euBox) return;
    const list = euBox.querySelector('.fc-eu-prices-list');
    if (!list) return;

    if (!prices || prices.length === 0) {
        list.innerHTML = '<div class="fc-no-eu-price">Fiyat verisi yok.</div>';
        return;
    }

    // Tablo başlıklarını ekle
    list.innerHTML = `
        <table class="fc-eu-market-table">
            <thead>
                <tr>
                    <th>Ülke</th>
                    <th>Adet</th>
                    <th>Fiyat</th>
                </tr>
            </thead>
            <tbody>
                ${prices.map(p => {
                    const flag = countryFlags[p.market] || '';
                    const domain = marketDomains[p.market] || 'com';
                    const productUrl = `https://www.amazon.${domain}/dp/${asin}`;
                    return `
                        <tr>
                            <td>${flag} ${p.market}</td>
                            <td>${p.moq}</td>
                            <td><a href="${productUrl}" target="_blank">${formatCurrency(p.price, p.currency || 'EUR')}</a></td>
                        </tr>
                    `;
                }).join('')}
            </tbody>
        </table>
    `;
}

// --- BACKGROUND'DAN GELEN MESAJLARI DİNLE ---
chrome.runtime && chrome.runtime.onMessage && chrome.runtime.onMessage.addListener((msg) => {
    if (msg.action === 'euMarketPrices' && msg.asin) {
        let container = document.getElementById('fastchecker-product-ui');
        if (!container) container = createUIContainer();
        renderEuMarketPrices(container, msg.asin, msg.prices);
    }
});

// Sayfa yüklendiğinde otomatik başlatıcı
(function() {
    const asin = getAsinFromUrl();
    if (!asin) return;
    const container = createUIContainer();
    if (!container) return;
    
    // Backend'den veri çek
    fetch(`https://web-production-e38b7.up.railway.app/get_product_details/${asin}?marketplace=US`)
        .then(r => r.json())
        .then(data => {
            if (data.error) {
                updateUI(container, {}, data.error);
            } else {
                updateUI(container, data);
            }
        })
        .catch(e => updateUI(container, {}, e.message));

    // --- EU MARKET FİYATLARI ALANI HER ZAMAN OLUŞSUN ---
    renderEuMarketPrices(container, asin, []); // Başlangıçta boş tablo göster
    // --- EU MARKET FİYATLARI İSTEĞİ ---
    chrome.runtime && chrome.runtime.sendMessage && chrome.runtime.sendMessage({
        action: 'fetchEuMarketPrices',
        asin: asin,
        markets: ['DE', 'FR', 'IT', 'ES', 'NL']
    }, (resp) => {
        if (resp && !resp.success) {
            console.warn('EU market fiyat isteği başarısız:', resp.error);
        }
    });
})();
