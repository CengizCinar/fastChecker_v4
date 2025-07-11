// background.js

// Orijinal helper scriptin import ediliyor.
importScripts('sp-api-helper.js');

let ws;
let isCheckStopped = false;

// --- SENİN ORİJİNAL WEBSOCKET KODUN ---
function connectWebSocket() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
        console.log("BACKGROUND: WebSocket bağlantısı aktif.");
        return;
    }
    const wsUrl = "wss://fastcheckerwebsocket-production.up.railway.app/";
    ws = new WebSocket(wsUrl);
    ws.onopen = () => console.log("BACKGROUND: WebSocket bağlantısı başarıyla kuruldu.");
    ws.onmessage = async (event) => {
        try {
            const msg = JSON.parse(event.data);
            if (msg.type === 'manual-result' && msg.asin && msg.manual_status) {
                console.log("BACKGROUND: Manuel sonuç alındı:", msg);
                const { manualResultsStore = {} } = await chrome.storage.local.get('manualResultsStore');
                manualResultsStore[msg.asin] = msg.manual_status;
                await chrome.storage.local.set({ manualResultsStore });
                console.log(`BACKGROUND: ${msg.asin} durumu (${msg.manual_status}) kalıcı hafızaya kaydedildi.`);
                chrome.runtime.sendMessage({ action: 'manualResult', result: msg });
            }
        } catch (e) { console.error('BACKGROUND: WebSocket mesajı işlenemedi:', e); }
    };
    ws.onclose = () => { console.warn("BACKGROUND: WebSocket koptu, 10 sn sonra tekrar denenecek."); ws = null; setTimeout(connectWebSocket, 10000); };
    ws.onerror = (err) => { console.error("BACKGROUND: WebSocket hatası:", err); ws.close(); };
}

// --- EU MARKET FİYATLARI İÇİN YENİ WEBSOCKET KODU (FastChecker_v4 copy 2'den kopyalandı) ---
let priceTrackerWs;
let priceTrackerMessageQueue = []; // Mesaj kuyruğu
let asinToTabIdMap = {}; // ASIN'i Tab ID ile eşleştiren harita

function connectPriceTrackerWebSocket() {
    if (priceTrackerWs && (priceTrackerWs.readyState === WebSocket.OPEN || priceTrackerWs.readyState === WebSocket.CONNECTING)) {
        console.log("BACKGROUND: Fiyat Takip WebSocket bağlantısı zaten aktif veya kuruluyor.");
        return;
    }

    const wsUrl = "wss://eu-price-automation-production.up.railway.app/";
    priceTrackerWs = new WebSocket(wsUrl);

    priceTrackerWs.onopen = () => {
        console.log("BACKGROUND: Fiyat Takip WebSocket bağlantısı başarıyla kuruldu.");
        while (priceTrackerMessageQueue.length > 0) {
            const message = priceTrackerMessageQueue.shift();
            console.log("BACKGROUND: Kuyruktaki mesaj gönderiliyor:", message);
            priceTrackerWs.send(JSON.stringify(message));
        }
    };

    priceTrackerWs.onmessage = async (event) => {
        console.log("BACKGROUND: WebSocket'ten HAM VERİ alındı:", event.data);
        try {
            const msg = JSON.parse(event.data);
            console.log("BACKGROUND: Fiyat Takip'ten İŞLENMİŞ MESAJ alındı:", msg);

            if (msg.type === 'eu-market-result' && msg.asin && msg.prices) {
                console.log(`BACKGROUND: 'eu-market-result' tipi mesaj doğrulandı. ASIN: ${msg.asin}`);
                const tabId = asinToTabIdMap[msg.asin];

                if (tabId) {
                    console.log(`BACKGROUND: Mesaj, kaydedilen TAB ID ${tabId}'ye gönderiliyor.`);
                    chrome.tabs.sendMessage(tabId, {
                        action: 'euMarketPrices',
                        asin: msg.asin,
                        prices: msg.prices
                    }, (response) => {
                        if (chrome.runtime.lastError) {
                            console.error(`BACKGROUND: Tab ${tabId} mesaj gönderilirken hata oluştu:`, chrome.runtime.lastError.message);
                        } else {
                            console.log(`BACKGROUND: Tab ${tabId} mesajı başarıyla aldı.`);
                        }
                    });
                    delete asinToTabIdMap[msg.asin];
                } else {
                    console.error(`BACKGROUND: ${msg.asin} için kayıtlı bir sekme ID'si bulunamadı.`);
                }
            }
        } catch (e) {
            console.error('BACKGROUND: Fiyat Takip WebSocket mesajı işlenemedi:', e);
        }
    };

    priceTrackerWs.onclose = () => {
        console.warn("BACKGROUND: Fiyat Takip WebSocket koptu, 10 sn sonra tekrar denenecek.");
        priceTrackerWs = null;
        setTimeout(connectPriceTrackerWebSocket, 10000);
    };

    priceTrackerWs.onerror = (err) => {
        console.error("BACKGROUND: Fiyat Takip WebSocket hatası:", err);
        priceTrackerWs.close();
    };
}

// --- SENİN ORİJİNAL ANA İŞLEVLERİN ---
chrome.runtime.onInstalled.addListener(() => {
    connectWebSocket();
    connectPriceTrackerWebSocket(); // Yeni eklenen
});
chrome.runtime.onStartup.addListener(() => {
    connectWebSocket();
    connectPriceTrackerWebSocket(); // Yeni eklenen
});

chrome.action.onClicked.addListener((tab) => {
    chrome.sidePanel.open({ tabId: tab.id });
});

// --- MESAJ DİNLEYİCİ (TÜM BLOKLAR TEK VE DOĞRU BİR YAPI İÇİNDE) ---
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    
    // 1. MEVCUT YAN PANEL ÖZELLİĞİ
    if (request.action === 'checkAsin') {
        isCheckStopped = false;
        console.log("BACKGROUND: 'checkAsin' talebi alındı.");
        connectWebSocket();
        handleAsinCheck(request.data, sendResponse);
        return true; // Asenkron işlem
    }
    
    // 2. MEVCUT DURDURMA ÖZELLİĞİN
    if (request.action === 'stopCheck') {
        console.log("BACKGROUND: 'stopCheck' talebi alındı.");
        isCheckStopped = true;
        sendResponse({ success: true });
        return true;
    }

    // 3. YENİ ÜRÜN SAYFASI ÖZELLİĞİ (PYTHON BACKEND'E YÖNLENDİRİR)
    if (request.action === 'fetchProductDetails') {
        const { asin, marketplace } = request;
        fetch(`https://web-production-e38b7.up.railway.app/get_product_details/${asin}?marketplace=${marketplace}`)
            .then(response => {
                if (!response.ok) {
                    return response.json().then(errorData => {
                        throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
                    });
                }
                return response.json();
            })
            .then(data => {
                sendResponse({ success: !data.error, data: data, error: data.error });
            })
            .catch(e => {
                sendResponse({ success: false, error: e.message });
            });
        return true;
    }

    // 4. EU MARKET FİYATLARI İSTEĞİ (FastChecker_v4 copy 2'den kopyalandı)
    if (request.action === 'fetchEuMarketPrices' && request.asin) {
        const tabId = sender.tab.id;
        asinToTabIdMap[request.asin] = tabId;

        connectPriceTrackerWebSocket();
        const markets = request.markets || ['DE', 'FR', 'IT', 'ES'];
        const message = {
            type: "/eu-market-request",
            asin: request.asin,
            markets: markets
        };

        if (priceTrackerWs && priceTrackerWs.readyState === WebSocket.OPEN) {
            priceTrackerWs.send(JSON.stringify(message));
            sendResponse({ success: true });
        } else {
            priceTrackerMessageQueue.push(message);
            if (!priceTrackerWs || priceTrackerWs.readyState === WebSocket.CLOSED) {
                connectPriceTrackerWebSocket();
            }
            sendResponse({ success: false, error: 'EU Price WebSocket bağlantısı yok veya kuruluyor.' });
        }
        return true;
    }
});

// --- render websocket --- (Orijinal fonksiyon, dokunulmadı)
async function handleAsinCheck(data, sendResponse) {
    try {
        const { asins, credentials, sellerId, marketplace } = data;
        const spApiHelper = new SPAPIHelper();
        const postaKutusuAdresi = "https://fastcheckerwebsocket-production.up.railway.app/mektup-at";

        for (let i = 0; i < asins.length; i++) {
            if (isCheckStopped) {
                console.log(`BACKGROUND: İşlem ${i}. ASIN'de kullanıcı tarafından durduruldu.`);
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