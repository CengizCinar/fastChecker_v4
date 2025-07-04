// Gerekli kütüphaneler
const fastify = require('fastify')({ logger: false });
const WebSocket = require('ws');
const cors = require('@fastify/cors');

// Kurulum
fastify.register(cors, {});
const wss = new WebSocket.Server({ server: fastify.server });

// WebSocket Bağlantı Yönetimi
let clients = [];
wss.on('connection', (ws) => {
    console.log('[WS] Bir istemci bağlandı. Toplam:', clients.length + 1);
    clients.push(ws);
    ws.on('close', () => {
        clients = clients.filter(client => client !== ws);
        console.log('[WS] Bir istemci ayrıldı. Kalan:', clients.length);
    });
    ws.on('message', (data) => {
        console.log('[WS] Gelen mesaj:', data);
        try {
            const msg = JSON.parse(data);
            if (msg.type === 'manual-result') {
                console.log(`[WS SONUÇ] ASIN: ${msg.asin}, Durum: ${msg.manual_status}`);
                broadcast(msg, '[WS] Broadcast edilen mesaj:');
            } else {
                console.log('[WS] Bilinmeyen tipte mesaj:', msg);
            }d
        } catch (e) {
            console.log('[WS] Mesaj ayrıştırılamadı:', data);
        }
    });
});

// Anlık Mesaj Gönderme Fonksiyonu
function broadcast(message, logPrefix = '[Broadcast]') {
    clients.forEach(client => {
        if (client.readyState === WebSocket.OPEN) {
            client.send(JSON.stringify(message));
        }
    });
    console.log(logPrefix, JSON.stringify(message));
}

// Ana Sayfa Mesajı
fastify.get('/', async (request, reply) => {
    console.log('[HTTP] GET / çağrıldı');
    return { durum: "Otomasyon sunucusu aktif ve hazır." };
});

// 1. FastChecker'dan ASIN Alma Kapısı
fastify.post('/mektup-at', async (request, reply) => {
    const yeniAsin = request.body.asin;
    console.log('[HTTP] POST /mektup-at:', request.body);
    if (yeniAsin) {
        console.log(`[GELEN] Yeni ASIN alındı: ${yeniAsin}`);
        broadcast({ type: 'yeni-mektup', asin: yeniAsin }, '[HTTP] Broadcast edilen yeni-mektup:');
    }
    return { durum: "ASIN alındı ve otomasyona iletildi." };
});

// 2. Onay Asistanı'ndan Sonuç Raporu Alma Kapısı
fastify.post('/sonuc-raporla', async (request, reply) => {
    const sonuc = request.body;
    console.log('[HTTP] POST /sonuc-raporla:', sonuc);
    if (sonuc && sonuc.type === 'manual-result') {
        console.log(`[SONUÇ] ASIN: ${sonuc.asin}, Durum: ${sonuc.manual_status}`);
        broadcast(sonuc, '[HTTP] Broadcast edilen manual-result:');
    }
    return { durum: "Sonuç raporu alındı ve yayınlandı." };
});

// Sunucuyu Başlatma
const start = async () => {
    try {
        await fastify.listen({ port: process.env.PORT || 3000, host: '0.0.0.0' });
        console.log('Otomasyon sunucusu (fastify) aktif!');
    } catch (err) {
        process.exit(1);
    }
};
start();