// background.js

// Yan panel işlevleri için gerekli olan helper scripti import et
importScripts('sp-api-helper.js');

// --- Global Değişkenler ---
let ws; // Yan panel (manuel kontrol) için WebSocket
let isCheckStopped = false; // Yan paneldeki kontrolü durdurmak için flag

let priceTrackerWs; // Ürün sayfası (EU fiyatları) için WebSocket
let priceTrackerMessageQueue = [];
let asinToTabIdMap = {};

// --- WebSocket Bağlantı Fonksiyonları ---

// 1. Yan Panel için orijinal WebSocket
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

// 2. Ürün Sayfası (EU Fiyatları) için yeni WebSocket
function connectPriceTrackerWebSocket() {
    if (priceTrackerWs && (priceTrackerWs.readyState === WebSocket.OPEN || priceTrackerWs.readyState === WebSocket.CONNECTING)) {
        return;
    }
    const wsUrl = "wss://eu-price-automation-production.up.railway.app/";
    priceTrackerWs = new WebSocket(wsUrl);
    priceTrackerWs.onopen = () => {
        console.log("BG: Fiyat Takip WS Bağlantısı Kuruldu.");
        while (priceTrackerMessageQueue.length > 0) {
            priceTrackerWs.send(JSON.stringify(priceTrackerMessageQueue.shift()));
        }
    };
    priceTrackerWs.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            if (msg.type === 'eu-market-result' && msg.asin && msg.prices) {
                const tabId = asinToTabIdMap[msg.asin];
                if (tabId) {
                    chrome.tabs.sendMessage(tabId, { action: 'euMarketPrices', asin: msg.asin, prices: msg.prices });
                    delete asinToTabIdMap[msg.asin];
                }
            }
        } catch (e) { console.error('BG: Fiyat WS Mesajı İşlenemedi:', e); }
    };
    priceTrackerWs.onclose = () => { priceTrackerWs = null; setTimeout(connectPriceTrackerWebSocket, 10000); };
    priceTrackerWs.onerror = (err) => { console.error("BG: Fiyat WS Hatası:", err); priceTrackerWs.close(); };
}

// --- Başlangıç ve Kurulum Olayları ---
chrome.runtime.onInstalled.addListener(() => {
    connectWebSocket();
    connectPriceTrackerWebSocket();
});
chrome.runtime.onStartup.addListener(() => {
    connectWebSocket();
    connectPriceTrackerWebSocket();
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

    if (request.action === 'fetchEuMarketPrices' && request.asin) {
        const tabId = sender.tab.id;
        asinToTabIdMap[request.asin] = tabId;
        connectPriceTrackerWebSocket();
        const message = { type: "/eu-market-request", asin: request.asin, markets: request.markets || ['DE', 'FR', 'IT', 'ES', 'NL'] };

        if (priceTrackerWs && priceTrackerWs.readyState === WebSocket.OPEN) {
            priceTrackerWs.send(JSON.stringify(message));
        } else {
            priceTrackerMessageQueue.push(message);
            if (!priceTrackerWs || priceTrackerWs.readyState === WebSocket.CLOSED) {
                connectPriceTrackerWebSocket();
            }
        }
        sendResponse({ success: true });
        return true; 
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
