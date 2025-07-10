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
        // --- SELLERAMP TEKNİĞİ: KESİN ÇÖZÜM ---
        // 1. Adım: #rightCol'u, içindeki elementlerin kendisine göre konumlanabilmesi için
        // bir "konumlandırma çapası" (positioning anchor) yap.
        rightCol.style.position = 'relative';

        // 2. Adım: Kendi UI'ımızı #rightCol'un içine ekle.
        // CSS dosyamızdaki `position: absolute` kuralı geri kalan işi halledecek.
        rightCol.prepend(container);
    } else {
        // #rightCol bulunamazsa hata ver ve devam etme.
        console.error('FastChecker: Konumlandırma için #rightCol bulunamadı.');
        return null;
    }
    return container;
}

function formatCurrency(amount, currency) {
    if (typeof amount !== 'number') return 'N/A';
    const options = { style: 'currency', currency };
    switch (currency) {
        case 'USD': return amount.toLocaleString('en-US', options);
        case 'CAD': return amount.toLocaleString('en-CA', options);
        case 'GBP': return amount.toLocaleString('en-GB', options);
        case 'EUR': return amount.toLocaleString('de-DE', options); // Avrupa için genel bir format
        case 'AUD': return amount.toLocaleString('en-AU', options);
        default: return `${amount.toFixed(2)} ${currency}`;
    }
}

function truncateTitle(title, maxLength = 50) {
    if (!title || title.length <= maxLength) return title;
    return title.substr(0, title.lastIndexOf(' ', maxLength)) + '...';
}

function updateUI(container, data, error = null) {
    if (error) {
        container.innerHTML = `<div class="fc-header"><span></span><span class="fc-close">&times;</span></div><div class="fc-error">Hata: ${error}</div>`;
        container.querySelector('.fc-close').addEventListener('click', () => container.remove());
        return;
    }
    
    const sellableStatus = data.isSellable ? '<span class="fc-status fc-sellable">SATILABİLİR</span>' : '<span class="fc-status fc-not-sellable">ONAY GEREKLİ</span>';
    

    let sellersHtml = data.offers.map(offer => {
        const sellerId = offer.SellerId || 'N/A';
        const sellerLink = `https://www.amazon.com/sp?ie=UTF8&seller=${sellerId}`;
        const priceHtml = offer.IsBuyBoxWinner
            ? `<span class='fc-seller-price'><b>${formatCurrency(offer.ListingPrice.Amount, offer.ListingPrice.CurrencyCode)}</b></span>`
            : `<span class='fc-seller-price'>${formatCurrency(offer.ListingPrice.Amount, offer.ListingPrice.CurrencyCode)}</span>`;
        return `
        <div class="fc-seller-row">
            <span class="fc-seller-ffm">${offer.IsFulfilledByAmazon ? 'FBA' : 'FBM'}</span>
            <a href="${sellerLink}" target="_blank" class="fc-seller-id">${sellerId}</a>
            ${priceHtml}
        </div>
    `}).join('');
    if (!sellersHtml) sellersHtml = '<div class="fc-no-seller">Aktif teklif yok.</div>';

    container.innerHTML = `
        <div class="fc-header">
            <span>✨ FastChecker AI Analysis</span>
            <span class="fc-close">&times;</span>
        </div>
        <div class="fc-card fc-main-info">
            <div class="fc-main-info-3col">
                <div class="fc-main-col fc-main-img"><img class="fc-main-info-img" src="${data.imageUrl || ''}" alt="${data.title || ''}"></div>
                <div class="fc-main-col fc-main-asin-ean">
                    <div class="fc-main-asin"><b>ASIN:</b> ${data.asin}</div>
                    <div class="fc-main-ean"><b>EAN:</b> ${data.ean}</div>
                </div>
                <div class="fc-main-col fc-main-brand">
                    <div class="fc-main-brand-label"><b>Marka:</b></div>
                    <div class="fc-main-brand-name">${data.brand || 'N/A'}</div>
                </div>
            </div>
            <div class="fc-main-info-row">
                <div class="fc-main-dim"><b>Boyutlar:</b> ${data.dimensions}</div>
                <div class="fc-main-weight"><b>Ağırlık:</b> ${data.packageWeight}</div>
            </div>
            <div class="fc-main-restriction">${sellableStatus}</div>
        </div>

        <div class="fc-card fc-finance-calculator">
            <div class="fc-card-header"><span>Profit Calculator</span></div>
            <div class="fc-input-row">
                <div class="input-group">
                    <label for="bsrInput">BSR</label>
                    <input type="text" id="bsrInput" value="N/A" readonly>
                </div>
                <div class="input-group">
                    <label for="estimatedSalesInput">Estimated Sales</label>
                    <input type="text" id="estimatedSalesInput" value="N/A" readonly>
                </div>
            </div>
            <div class="fc-input-row">
                <div class="input-group">
                    <label for="costInput">Cost</label>
                    <input type="text" inputmode="decimal" pattern="[0-9]*" id="costInput" value="0" autocomplete="off" style="appearance: textfield;">
                </div>
                <div class="input-group">
                    <label for="saleInput">Sale</label>
                    <input type="text" inputmode="decimal" pattern="[0-9]*" id="saleInput" value="0" autocomplete="off" style="appearance: textfield;">
                </div>
            </div>

            <div class="fc-result-row">
                <div class="result-item">
                    <span>Profit</span>
                    <span id="profitResult" class="calculated-value">0.00</span>
                </div>
                <div class="result-item">
                    <span>R.O.I</span>
                    <span id="roiResult" class="calculated-value">0.00%</span>
                </div>
                <div class="result-item">
                    <span>Breakeven</span>
                    <span id="breakevenResult" class="calculated-value">0.00</span>
                </div>
            </div>

            <div class="fc-fee-details">
                <span id="referralFeeDisplay">Referral Fee: ${formatCurrency(data.referralFee, data.currencyCode)}</span>
                <span id="fbaFeeDisplay">FBA Fee: ${formatCurrency(data.fbaFee, data.currencyCode)}</span>
            </div>
        </div>

        <div class="fc-card fc-sellers">
            <div class="fc-card-header">
                <span class="icon">📦</span><h4>Satıcılar (${data.offers.length})</h4>
            </div>
            <div class="fc-seller-list">${sellersHtml}</div>
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
    let euBox = container.querySelector('#fc-eu-market-prices');
    if (!euBox) {
        euBox = document.createElement('div');
        euBox.id = 'fc-eu-market-prices';
        euBox.className = 'fc-card fc-eu-market-prices';
        euBox.innerHTML = `
            <div class="fc-card-header">
                <span class="icon">🇪🇺</span><h4>EU Market Fiyatları</h4>
            </div>
            <div class="fc-eu-prices-list" style="max-height: 120px; overflow-y: auto;"></div>
        `;
        container.appendChild(euBox);
    }
    const list = euBox.querySelector('.fc-eu-prices-list');
    if (!prices || prices.length === 0) {
        list.innerHTML = '<div class="fc-no-eu-price">Fiyat verisi yok.</div>';
        return;
    }
    list.innerHTML = prices.map(p =>
        `<div class="fc-eu-price-row"><b>${p.market}</b> - MOQ: ${p.moq} - <span>${formatCurrency(p.price, p.currency || 'EUR')}</span></div>`
    ).join('');
}

// --- BACKGROUND'DAN GELEN MESAJLARI DİNLE ---
chrome.runtime && chrome.runtime.onMessage && chrome.runtime.onMessage.addListener((msg) => {
    if (msg.action === 'euMarketPrices' && msg.asin) {
        // UI container'ı bul
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
    // --- EU MARKET FİYATLARI İSTEĞİ ---
    chrome.runtime && chrome.runtime.sendMessage && chrome.runtime.sendMessage({
        action: 'fetchEuMarketPrices',
        asin: asin,
        markets: ['DE', 'FR', 'IT', 'ES', 'NL']
    }, (resp) => {
        if (resp && !resp.success) {
            // Hata logla, UI'ya yazmaya gerek yok
            console.warn('EU market fiyat isteği başarısız:', resp.error);
        }
    });
})();
