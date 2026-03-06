const express = require('express');
const axios = require('axios');
const qrcode = require('qrcode');
const pino = require('pino');
const {
    default: makeWASocket,
    DisconnectReason,
    fetchLatestBaileysVersion,
    useMultiFileAuthState,
} = require('@whiskeysockets/baileys');
const { Boom } = require('@hapi/boom');

const app = express();
app.use(express.json());

const PORT = process.env.PORT || 3000;
const WEBHOOK_URL = process.env.WEBHOOK_URL || 'http://localhost:8000/webhook';
const AUTH_FOLDER = process.env.BAILEYS_AUTH_FOLDER || './baileys_auth';

let sock = null;
let isConnected = false;
let connectedNumber = null;
let latestQrCode = null;

function formatPhoneFromJid(jid) {
    return jid?.replace('@s.whatsapp.net', '') || null;
}

function parseIncomingText(message) {
    if (!message) return null;

    if (message.conversation) return message.conversation;
    if (message.extendedTextMessage?.text) return message.extendedTextMessage.text;
    if (message.imageMessage?.caption) return message.imageMessage.caption;
    if (message.videoMessage?.caption) return message.videoMessage.caption;

    return null;
}

async function startBaileys() {
    const { state, saveCreds } = await useMultiFileAuthState(AUTH_FOLDER);
    const { version } = await fetchLatestBaileysVersion();

    sock = makeWASocket({
        version,
        auth: state,
        printQRInTerminal: false,
        logger: pino({ level: 'warn' }),
    });

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('connection.update', async (update) => {
        const { connection, lastDisconnect, qr } = update;

        if (qr) {
            latestQrCode = await qrcode.toDataURL(qr);
            console.log('QR Code gerado — acesse GET /qr para escanear');
        }

        if (connection === 'open') {
            isConnected = true;
            latestQrCode = null;
            connectedNumber = formatPhoneFromJid(sock.user?.id);
            console.log(`WhatsApp conectado! Número: ${connectedNumber || 'indisponível'}`);
        }

        if (connection === 'close') {
            isConnected = false;
            connectedNumber = null;

            const statusCode = new Boom(lastDisconnect?.error)?.output?.statusCode;
            const shouldReconnect = statusCode !== DisconnectReason.loggedOut;

            console.log(`WhatsApp desconectado. Código: ${statusCode}. Reconectar: ${shouldReconnect}`);

            if (shouldReconnect) {
                await startBaileys();
            } else {
                console.log('Sessão encerrada (loggedOut). Gere novo QR em /qr para autenticar novamente.');
            }
        }
    });

    sock.ev.on('messages.upsert', async ({ type, messages }) => {
        if (type !== 'notify') return;

        const message = messages?.[0];
        if (!message || message.key.fromMe) return;

        const remoteJid = message.key.remoteJid;
        if (!remoteJid || !remoteJid.endsWith('@s.whatsapp.net')) return;

        const text = parseIncomingText(message.message);
        if (!text) return;

        const payload = {
            from: formatPhoneFromJid(remoteJid),
            text,
            name: message.pushName || 'Usuário',
        };

        try {
            console.log(`Mensagem recebida de ${payload.from}: ${payload.text}`);
            await axios.post(WEBHOOK_URL, payload);
        } catch (error) {
            console.error('Erro ao enviar para webhook:', error.message);
        }
    });
}

app.get('/qr', (req, res) => {
    if (!latestQrCode) {
        return res.send('<h2>✅ WhatsApp já conectado ou aguardando novo QR.</h2>');
    }

    res.send(`
        <html>
            <body style="display:flex;justify-content:center;align-items:center;height:100vh;flex-direction:column">
                <h2>Escaneie o QR Code</h2>
                <img src="${latestQrCode}" />
                <p>Atualize a página se o QR expirar</p>
            </body>
        </html>
    `);
});

app.get('/status', (req, res) => {
    res.json({
        connected: isConnected,
        number: connectedNumber,
    });
});

app.post('/send-message', async (req, res) => {
    if (ADAPTER_API_KEY && req.headers['x-api-key'] !== ADAPTER_API_KEY) {
        return res.status(401).json({ error: 'Unauthorized' });
    }

    const { to, text } = req.body;

    if (!to || !text) {
        return res.status(400).json({ error: 'Parâmetros "to" e "text" são obrigatórios' });
    }

    if (!sock || !isConnected) {
        return res.status(503).json({ error: 'WhatsApp não conectado' });
    }

    try {
        const jid = to.includes('@s.whatsapp.net') ? to : `${to}@s.whatsapp.net`;
        await sock.sendMessage(jid, { text });
        console.log(`Mensagem enviada para ${to}: ${text}`);
        return res.json({ success: true });
    } catch (error) {
        console.error('Erro ao enviar mensagem:', error);
        return res.status(500).json({ error: 'Falha ao enviar mensagem' });
    }
});

app.listen(PORT, async () => {
    console.log(`Servidor Baileys rodando na porta ${PORT}`);
    await startBaileys();
});
