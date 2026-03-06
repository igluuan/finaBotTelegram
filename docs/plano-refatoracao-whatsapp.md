# Plano de refatoração WhatsApp (migração para Baileys)

## Objetivo
Remover dependências legadas (`whatsapp-web.js` + Puppeteer/Chromium) e padronizar a integração com a API atual do **Baileys** (`@whiskeysockets/baileys`), mantendo compatibilidade com o backend Python existente.

## Escopo analisado
- `finbot-baileys/server.js`
- `finbot-baileys/package.json`
- `finbot-baileys/Dockerfile`
- `finbot/whatsapp/client.py`
- `finbot/whatsapp/webhook.py`
- `finbot/whatsapp/schemas.py`
- `tests/whatsapp/test_whatsapp.py`

## Plano de execução (objetivo e direto)

### Fase 1 — Remoção de legado
1. Remover `whatsapp-web.js` e toda dependência de navegador (`puppeteer/chromium`) do adaptador Node.
2. Eliminar configuração de autenticação antiga (`LocalAuth`, `@c.us`) e eventos específicos da biblioteca legada.

### Fase 2 — Nova base Baileys
1. Implementar sessão com `useMultiFileAuthState` para persistência segura dos dados de autenticação.
2. Usar `fetchLatestBaileysVersion` para manter compatibilidade de protocolo.
3. Controlar ciclo de conexão via `connection.update` com reconexão automática (exceto `loggedOut`).
4. Gerar QR de autenticação com `qrcode` e expor no endpoint `/qr`.

### Fase 3 — Compatibilidade com o backend atual
1. Manter contrato HTTP com o Python:
   - Entrada no adaptador: `POST /send-message` com `{ to, text }`.
   - Saída para webhook Python: `{ from, text, name }`.
2. Normalizar JID para padrão Baileys (`@s.whatsapp.net`).
3. Processar mensagens recebidas (`messages.upsert`) e extrair texto de formatos comuns (`conversation`, `extendedTextMessage`, `caption`).

### Fase 4 — Hardening operacional
1. Expor `/status` com estado de conexão real (`connected`, `number`).
2. Retornar `503` em envio quando socket estiver desconectado.
3. Ajustar imagem Docker para remover dependências desnecessárias de browser.

### Fase 5 — Validação
1. Validar testes Python existentes (especialmente cliente WhatsApp).
2. Verificar inicialização do adaptador Node (`npm install`, `node --check server.js`).
3. Validar contrato de endpoints (`/status`, `/qr`, `/send-message`).

## Implementação aplicada
- ✅ Migração completa do adaptador Node para `@whiskeysockets/baileys`.
- ✅ Remoção de dependências antigas de WhatsApp web + Chromium.
- ✅ Preservação do contrato com o backend Python para não quebrar handlers atuais.
- ✅ Reconexão automática e controle de estado de conexão.

## Próximos passos recomendados
1. Adicionar teste de integração do adaptador Node (mockando webhook).
2. Adicionar suporte a mídia/áudio no parser de entrada (se necessário para produto).
3. Versionar diretório de auth em volume Docker dedicado para produção.
