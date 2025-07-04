// background.js

// Orijinal helper scriptin import ediliyor.
importScripts('sp-api-helper.js');

let ws;
let isCheckStopped = false;

// --- SENİN ORİJİNAL WEBSOCKET KODUN (DOKUNULMADI) ---
function connectWebSocket() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
        console.log("BACKGROUND: WebSocket bağlantısı zaten aktif.");
        return;
    }
    const wsUrl = "wss://fastchecker-websocket.onrender.com";
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

// --- SENİN ORİJİNAL ANA İŞLEVLERİN (DOKUNULMADI) ---
chrome.runtime.onInstalled.addListener(connectWebSocket);
chrome.runtime.onStartup.addListener(connectWebSocket);

chrome.action.onClicked.addListener((tab) => {
    chrome.sidePanel.open({ tabId: tab.id });
}); // <<< Hatanın bir kaynağı da buradaydı, parantez eksikti.


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
        const { asin, marketplace } = request; // marketplace'i request'ten al
        // API URL'ine marketplace'i ekle
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
                if (data.error) {
                    sendResponse({ success: false, error: data.error });
                } else {
                    sendResponse({ success: true, data: data });
                }
            })
            .catch(e => {
                sendResponse({ success: false, error: e.message });
            });
        return true; // Asenkron yanıt için
    }
});


// --- SENİN ORİJİNAL handleAsinCheck FONKSİYONUN (DOKUNULMADI) ---
async function handleAsinCheck(data, sendResponse) {
    try {
        const { asins, credentials, sellerId, marketplace } = data;
        const spApiHelper = new SPAPIHelper();
        const postaKutusuAdresi = "https://fastcheckerwebsocket.glitch.me/mektup-at";

        for (let i = 0; i < asins.length; i++) {
            if (isCheckStopped) {
                console.log(`BACKGROUND: İşlem ${i}. ASIN'de kullanıcı tarafından durduruldu.`);
                chrome.runtime.sendMessage({ action: 'asinCheckDone', stopped: true });
                return;
            }
            const asin = asins[i];
            // Burası senin orijinal helper'ını kullanıyor.
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