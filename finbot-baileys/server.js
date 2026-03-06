const {
    default: makeWASocket,
    useMultiFileAuthState,
    DisconnectReason
} = require('@whiskeysockets/baileys');
const express = require('express');
const axios = require('axios');
const qrcode = require('qrcode-terminal');
const pino = require('pino');

const app = express();
app.use(express.json());

const PORT = 3000;
const WEBHOOK_URL = 'http://localhost:8000/webhook';

let sock; // Global socket instance

async function connectToWhatsApp() {
    const { state, saveCreds } = await useMultiFileAuthState('auth_info_baileys');

    sock = makeWASocket({
        logger: pino({ level: 'silent' }),
        printQRInTerminal: true,
        auth: state,
    });

    sock.ev.on('connection.update', (update) => {
        const { connection, lastDisconnect, qr } = update;
        
        if (qr) {
            qrcode.generate(qr, { small: true });
        }

        if (connection === 'close') {
            const shouldReconnect = (lastDisconnect.error)?.output?.statusCode !== DisconnectReason.loggedOut;
            console.log('Conexão fechada devido a ', lastDisconnect.error, ', reconectando ', shouldReconnect);
            if (shouldReconnect) {
                connectToWhatsApp();
            }
        } else if (connection === 'open') {
            console.log('Conexão aberta com sucesso!');
        }
    });

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('messages.upsert', async ({ messages, type }) => {
        if (type === 'notify') {
            for (const msg of messages) {
                if (!msg.key.fromMe) {
                    try {
                        const messageContent = msg.message.conversation || msg.message.extendedTextMessage?.text;
                        
                        if (messageContent) {
                            const payload = {
                                from: msg.key.remoteJid.replace('@s.whatsapp.net', ''),
                                text: messageContent,
                                name: msg.pushName || 'Usuário'
                            };

                            console.log(`Mensagem recebida de ${payload.from}: ${payload.text}`);
                            await axios.post(WEBHOOK_URL, payload);
                        }
                    } catch (error) {
                        console.error('Erro ao enviar para webhook:', error.message);
                    }
                }
            }
        }
    });
}

// Endpoint para enviar mensagens
app.post('/send-message', async (req, res) => {
    const { to, text } = req.body;
    
    if (!to || !text) {
        return res.status(400).json({ error: 'Parâmetros "to" e "text" são obrigatórios' });
    }

    try {
        const jid = to.includes('@s.whatsapp.net') ? to : `${to}@s.whatsapp.net`;
        if (sock) {
            await sock.sendMessage(jid, { text: text });
            console.log(`Mensagem enviada para ${to}: ${text}`);
            res.json({ success: true });
        } else {
            res.status(503).json({ error: 'WhatsApp não conectado' });
        }
    } catch (error) {
        console.error('Erro ao enviar mensagem:', error);
        res.status(500).json({ error: 'Falha ao enviar mensagem' });
    }
});

connectToWhatsApp();

app.listen(PORT, () => {
    console.log(`Servidor Baileys rodando na porta ${PORT}`);
});
