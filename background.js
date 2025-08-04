// background.js (Nihai ve Sadece DE, FR, IT, ES için çalışan hali)

// Yan panel işlevleri için gerekli olan helper scripti import et
importScripts('sp-api-helper.js');

// --- Global Değişkenler ---
let ws; // SADECE Yan panel (manuel kontrol) için WebSocket
let isCheckStopped = false; // Yan paneldeki kontrolü durdurmak için flag

// --- WebSocket Bağlantı Fonksiyonu (Sadece Yan Panel için) ---
function connectWebSocket() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
        return;
    }
    const wsUrl = "wss://fastcheckerwebsocket-production.up.railway.app/";
    ws = new WebSocket(wsUrl);
    ws.onopen = () => console.log("BG: Manuel Kontrol WS Bağlantısı Kuruldu.");
    ws.onmessage = async (event) => {
        try {
            const msg = JSON.parse(event.data);
            if (msg.type === 'manual-result' && msg.asin && msg.manual_status) {
                const { manualResultsStore = {} } = await chrome.storage.local.get('manualResultsStore');
                manualResultsStore[msg.asin] = msg.manual_status;
                await chrome.storage.local.set({ manualResultsStore });
                chrome.runtime.sendMessage({ action: 'manualResult', result: msg });
            }
        } catch (e) { console.error('BG: Manuel Kontrol WS Mesajı İşlenemedi:', e); }
    };
    ws.onclose = () => { ws = null; setTimeout(connectWebSocket, 10000); };
    ws.onerror = (err) => { console.error("BG: Manuel Kontrol WS Hatası:", err); ws.close(); };
}


// --- Başlangıç ve Kurulum Olayları ---
chrome.runtime.onInstalled.addListener(() => {
    connectWebSocket();
});
chrome.runtime.onStartup.addListener(() => {
    connectWebSocket();
});

// Yan paneli açmak için action butonu
chrome.action.onClicked.addListener((tab) => {
    chrome.sidePanel.open({ tabId: tab.id });
});


// --- BİRLEŞTİRİLMİŞ ANA MESAJ DİNLEYİCİSİ ---
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {

    // --- Yan Panel İşlevleri ---
    if (request.action === 'checkAsin') {
        isCheckStopped = false;
        connectWebSocket();
        handleAsinCheck(request.data, sendResponse);
        return true; // Asenkron
    }

    if (request.action === 'stopCheck') {
        isCheckStopped = true;
        sendResponse({ success: true });
        return true;
    }

    // --- Ürün Sayfası (Content Script) İşlevleri ---
    if (request.action === 'fetchProductDetails') {
        const { asin, marketplace } = request;
        const tabId = sender.tab.id;

        fetch(`https://web-production-e38b7.up.railway.app/get_product_details/${asin}?marketplace=${marketplace}`)
            .then(response => response.json())
            .then(data => {
                chrome.tabs.sendMessage(tabId, { action: 'displayProductDetails', asin: asin, data: data });
                sendResponse({ success: true });
            })
            .catch(error => {
                chrome.tabs.sendMessage(tabId, { action: 'displayProductDetails', asin: asin, data: { error: error.message } });
                sendResponse({ success: false, error: error.message });
            });
        return true; // Asenkron
    }

    // --- EU FİYAT ALMA MANTIĞI (API İLE) ---
    if (request.action === 'fetchEuMarketPrices' && request.asin) {
        const { asin, markets } = request;
        const tabId = sender.tab.id;
        
        // --- DEĞİŞİKLİK BURADA ---
        // Varsayılan market listesinden 'GB' kaldırıldı.
        const marketsToFetch = markets || ['DE', 'FR', 'IT', 'ES'];
        const marketsQuery = marketsToFetch.join(',');
        
        fetch(`https://web-production-e38b7.up.railway.app/get_eu_business_prices/${asin}?markets=${marketsQuery}`)
            .then(response => response.json())
            .then(data => {
                chrome.tabs.sendMessage(tabId, { action: 'euMarketPrices', asin: asin, prices: data.prices });
                sendResponse({ success: true });
            })
            .catch(error => {
                console.error('BG: EU Business Fiyatları alınamadı:', error);
                chrome.tabs.sendMessage(tabId, { action: 'euMarketPrices', asin: asin, prices: [] });
                sendResponse({ success: false, error: error.message });
            });
        return true; // Asenkron
    }
});


// --- Yan Panel için ASIN Kontrol Yardımcı Fonksiyonu ---
async function handleAsinCheck(data, sendResponse) {
    try {
        const { asins, credentials, sellerId, marketplace } = data;
        const spApiHelper = new SPAPIHelper();
        const postaKutusuAdresi = "https://fastcheckerwebsocket-production.up.railway.app/mektup-at";

        for (let i = 0; i < asins.length; i++) {
            if (isCheckStopped) {
                chrome.runtime.sendMessage({ action: 'asinCheckDone', stopped: true });
                return;
            }
            const asin = asins[i];
            let result = await spApiHelper.checkASINSellability(asin, credentials, sellerId, marketplace);
            
            const isApprovalRequired = result.details?.reasons?.some(r => r.reasonCode === 'APPROVAL_REQUIRED');
            if (isApprovalRequired) {
                result.manual_check_pending = true;
                fetch(postaKutusuAdresi, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ asin: result.asin })
                }).catch(error => console.error('Sunucuya gönderirken hata:', error));
            }

            chrome.runtime.sendMessage({ action: 'asinResult', result: result });
            if (i < asins.length - 1) {
                await new Promise(resolve => setTimeout(resolve, 500));
            }
        }
        chrome.runtime.sendMessage({ action: 'asinCheckDone', stopped: false });
        sendResponse({ success: true });
    } catch (error) {
        sendResponse({ success: false, error: error.message });
    }
}