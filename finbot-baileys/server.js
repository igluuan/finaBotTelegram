const { Client, LocalAuth } = require('whatsapp-web.js');
const express = require('express');
const axios = require('axios');
const qrcode = require('qrcode');

const app = express();
app.use(express.json());

const PORT = process.env.PORT || 3000;
const WEBHOOK_URL = process.env.WEBHOOK_URL || 'http://localhost:8000/webhook';

// ── Cliente WhatsApp ──────────────────────────────────────────

const client = new Client({
    authStrategy: new LocalAuth({ dataPath: './wwebjs_auth' }),
    puppeteer: {
        executablePath: '/usr/bin/chromium-browser', // ajustar se necessário
        headless: true,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu',
        ],
    },
});

client.on('qr', async (qr) => {
    console.log('QR Code gerado — acesse GET /qr para escanear');
    // Salva QR em memória para expor via endpoint
    app.locals.qrCode = await qrcode.toDataURL(qr);
});

client.on('ready', () => {
    console.log('WhatsApp conectado!');
    app.locals.qrCode = null;
});

client.on('disconnected', (reason) => {
    console.log('WhatsApp desconectado:', reason);
    client.initialize();
});

client.on('message', async (msg) => {
    if (msg.fromMe) return;
    try {
        const payload = {
            from: msg.from.replace('@c.us', ''),
            text: msg.body,
            name: msg._data?.notifyName || 'Usuário',
        };
        console.log(`Mensagem recebida de ${payload.from}: ${payload.text}`);
        await axios.post(WEBHOOK_URL, payload);
    } catch (error) {
        console.error('Erro ao enviar para webhook:', error.message);
    }
});

client.initialize();

// ── Endpoints ─────────────────────────────────────────────────

// Exibe QR Code para autenticação
app.get('/qr', (req, res) => {
    if (!app.locals.qrCode) {
        return res.send('<h2>✅ WhatsApp já conectado!</h2>');
    }
    res.send(`
        <html>
            <body style="display:flex;justify-content:center;align-items:center;height:100vh;flex-direction:column">
                <h2>Escaneie o QR Code</h2>
                <img src="${app.locals.qrCode}" />
                <p>Atualize a página se o QR expirar</p>
            </body>
        </html>
    `);
});

// Status da conexão
app.get('/status', (req, res) => {
    res.json({
        connected: client.info ? true : false,
        number: client.info?.wid?.user || null,
    });
});

// Enviar mensagem (chamado pelo Python)
app.post('/send-message', async (req, res) => {
    const { to, text } = req.body;
    if (!to || !text) {
        return res.status(400).json({ error: 'Parâmetros "to" e "text" são obrigatórios' });
    }
    try {
        const jid = to.includes('@c.us') ? to : `${to}@c.us`;
        await client.sendMessage(jid, text);
        console.log(`Mensagem enviada para ${to}: ${text}`);
        res.json({ success: true });
    } catch (error) {
        console.error('Erro ao enviar mensagem:', error);
        res.status(500).json({ error: 'Falha ao enviar mensagem' });
    }
});

app.listen(PORT, () => console.log(`Servidor wwebjs rodando na porta ${PORT}`));
