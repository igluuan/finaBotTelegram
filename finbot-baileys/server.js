const express = require('express');
const axios = require('axios');
const qrcode = require('qrcode');
const pino = require('pino');
const crypto = require('crypto');
const {
    default: makeWASocket,
    DisconnectReason,
    downloadContentFromMessage,
    fetchLatestBaileysVersion,
    useMultiFileAuthState,
} = require('@whiskeysockets/baileys');
const { Boom } = require('@hapi/boom');

const app = express();
app.use(express.json());

const PORT = process.env.PORT || 3000;
const WEBHOOK_URL = process.env.WEBHOOK_URL || 'http://localhost:8000/webhook';
const AUTH_FOLDER = process.env.BAILEYS_AUTH_FOLDER || './baileys_auth';
const ADAPTER_API_KEY = process.env.WHATSAPP_ADAPTER_API_KEY || '';
const WEBHOOK_SECRET = process.env.WHATSAPP_WEBHOOK_SECRET || '';

let sock = null;
let isConnected = false;
let connectedNumber = null;
let latestQrCode = null;

function formatPhoneFromJid(jid) {
    if (!jid) return null;
    return jid
        .replace('@s.whatsapp.net', '')
        .replace('@c.us', '')
        .replace('@lid', '');
}

function isSupportedUserJid(jid) {
    if (!jid) return false;
    return (
        jid.endsWith('@s.whatsapp.net')
        || jid.endsWith('@c.us')
        || jid.endsWith('@lid')
    );
}

function extractSenderId(message) {
    const remoteJid = message?.key?.remoteJid || null;
    const participantJid = message?.key?.participant || null;

    if (isSupportedUserJid(remoteJid) && !remoteJid.endsWith('@lid')) {
        return formatPhoneFromJid(remoteJid);
    }
    if (isSupportedUserJid(participantJid)) {
        return formatPhoneFromJid(participantJid);
    }
    if (isSupportedUserJid(remoteJid)) {
        return formatPhoneFromJid(remoteJid);
    }
    return null;
}

function unwrapMessageContent(message) {
    let current = message;
    // Some message types wrap the real payload in nested containers.
    while (current) {
        if (current.ephemeralMessage?.message) {
            current = current.ephemeralMessage.message;
            continue;
        }
        if (current.viewOnceMessageV2?.message) {
            current = current.viewOnceMessageV2.message;
            continue;
        }
        if (current.viewOnceMessage?.message) {
            current = current.viewOnceMessage.message;
            continue;
        }
        if (current.documentWithCaptionMessage?.message) {
            current = current.documentWithCaptionMessage.message;
            continue;
        }
        break;
    }
    return current;
}

function parseIncomingText(message) {
    const normalized = unwrapMessageContent(message);
    if (!normalized) return null;
    if (normalized.conversation) return normalized.conversation;
    if (normalized.extendedTextMessage?.text) return normalized.extendedTextMessage.text;
    if (normalized.imageMessage?.caption) return normalized.imageMessage.caption;
    if (normalized.videoMessage?.caption) return normalized.videoMessage.caption;
    if (normalized.documentMessage?.caption) return normalized.documentMessage.caption;
    return null;
}

async function streamToBase64(stream) {
    const chunks = [];
    for await (const chunk of stream) {
        chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
    }
    return Buffer.concat(chunks).toString('base64');
}

async function extractIncomingPayload(message) {
    const normalized = unwrapMessageContent(message);
    if (!normalized) return null;

    const text = parseIncomingText(normalized);
    if (text) {
        return {
            text,
            media_type: 'text',
        };
    }

    if (normalized.audioMessage) {
        try {
            const stream = await downloadContentFromMessage(normalized.audioMessage, 'audio');
            const mediaBase64 = await streamToBase64(stream);
            return {
                text: '',
                media_type: 'audio',
                mime_type: normalized.audioMessage.mimetype || 'audio/ogg',
                media_base64: mediaBase64,
                file_length: normalized.audioMessage.fileLength
                    ? Number(normalized.audioMessage.fileLength)
                    : null,
                voice_note: Boolean(normalized.audioMessage.ptt),
            };
        } catch (error) {
            console.error('Failed to extract audio payload:', error.message);
            return {
                text: '',
                media_type: 'audio',
                mime_type: normalized.audioMessage.mimetype || 'audio/ogg',
                media_base64: null,
                file_length: normalized.audioMessage.fileLength
                    ? Number(normalized.audioMessage.fileLength)
                    : null,
                voice_note: Boolean(normalized.audioMessage.ptt),
            };
        }
    }

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
            console.log('QR code generated - open GET /qr');
        }

        if (connection === 'open') {
            isConnected = true;
            latestQrCode = null;
            connectedNumber = formatPhoneFromJid(sock.user?.id);
            console.log(`WhatsApp connected: ${connectedNumber || 'unknown'}`);
        }

        if (connection === 'close') {
            isConnected = false;
            connectedNumber = null;

            const statusCode = new Boom(lastDisconnect?.error)?.output?.statusCode;
            const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
            console.log(`WhatsApp disconnected. code=${statusCode} reconnect=${shouldReconnect}`);

            if (shouldReconnect) {
                await startBaileys();
            } else {
                console.log('Session logged out. Re-auth with /qr');
            }
        }
    });

    sock.ev.on('messages.upsert', async ({ type, messages }) => {
        if (type !== 'notify') {
            return;
        }

        const message = messages?.[0];
        if (!message) {
            console.log('Ignoring upsert with empty message payload');
            return;
        }
        if (message.key.fromMe) {
            console.log('Ignoring own outgoing message (fromMe=true)');
            return;
        }

        const remoteJid = message.key.remoteJid;
        if (!isSupportedUserJid(remoteJid)) {
            console.log(`Ignoring non-user jid: ${remoteJid || 'unknown'}`);
            return;
        }

        const incomingPayload = await extractIncomingPayload(message.message);
        if (!incomingPayload) {
            console.log(`Ignoring message without supported payload from ${remoteJid}`);
            return;
        }

        const senderId = extractSenderId(message);
        if (!senderId) {
            console.log(`Ignoring message with unresolved sender id. remoteJid=${remoteJid || 'unknown'}`);
            return;
        }

        const payload = {
            from: senderId,
            reply_to: remoteJid,
            text: incomingPayload.text,
            media_type: incomingPayload.media_type || 'text',
            mime_type: incomingPayload.mime_type || null,
            media_base64: incomingPayload.media_base64 || null,
            file_length: incomingPayload.file_length || null,
            voice_note: incomingPayload.voice_note || false,
            name: message.pushName || 'Usuario',
            message_id: message.key.id || null,
            timestamp: Number(message.messageTimestamp) || Math.floor(Date.now() / 1000),
        };

        try {
            const rawBody = JSON.stringify(payload);
            const headers = { 'Content-Type': 'application/json' };
            if (WEBHOOK_SECRET) {
                headers['X-Signature'] = crypto
                    .createHmac('sha256', WEBHOOK_SECRET)
                    .update(rawBody)
                    .digest('hex');
            }

            console.log(`Incoming ${payload.media_type} message from ${payload.from}: ${payload.text || '[media]'}`);
            await axios.post(WEBHOOK_URL, rawBody, {
                headers,
                timeout: 5000,
            });
        } catch (error) {
            console.error('Failed to send webhook:', error.message);
        }
    });
}

app.get('/qr', (req, res) => {
    if (!latestQrCode) {
        return res.send('<h2>WhatsApp already connected or waiting for next QR.</h2>');
    }

    res.send(`
        <html>
            <body style="display:flex;justify-content:center;align-items:center;height:100vh;flex-direction:column">
                <h2>Scan QR code</h2>
                <img src="${latestQrCode}" />
                <p>Refresh if QR expires</p>
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
        return res.status(400).json({ error: 'Parameters "to" and "text" are required' });
    }

    if (!sock || !isConnected) {
        return res.status(503).json({ error: 'WhatsApp not connected' });
    }

    try {
        const jid = to.includes('@') ? to : `${to}@s.whatsapp.net`;
        await sock.sendMessage(jid, { text });
        console.log(`Message sent to ${to}: ${text}`);
        return res.json({ success: true });
    } catch (error) {
        console.error('Failed to send message:', error.message);
        return res.status(500).json({ error: 'Failed to send message' });
    }
});

app.post('/send-state-typing', async (req, res) => {
    if (ADAPTER_API_KEY && req.headers['x-api-key'] !== ADAPTER_API_KEY) {
        return res.status(401).json({ error: 'Unauthorized' });
    }

    const { to } = req.body;
    if (!to) {
        return res.status(400).json({ error: 'Parameter "to" is required' });
    }

    if (!sock || !isConnected) {
        return res.status(503).json({ error: 'WhatsApp not connected' });
    }

    try {
        const jid = to.includes('@') ? to : `${to}@s.whatsapp.net`;
        await sock.presenceSubscribe(jid);
        await sock.sendPresenceUpdate('composing', jid);
        return res.json({ success: true });
    } catch (error) {
        console.error('Failed to send typing state:', error.message);
        return res.status(500).json({ error: 'Failed to send typing state' });
    }
});

app.listen(PORT, async () => {
    console.log(`Baileys server running on port ${PORT}`);
    console.log(`Webhook target: ${WEBHOOK_URL}`);
    console.log(`Webhook signature enabled: ${Boolean(WEBHOOK_SECRET)}`);
    await startBaileys();
});
