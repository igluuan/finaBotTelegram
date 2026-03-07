# Fase 1 — Base Estrutural Confiável

## Objetivo
Estabelecer uma fundação estável para o bot de WhatsApp, privilegiando a confiabilidade do dia a dia (2 usuários) em vez de escalabilidade desnecessária. Nesta fase, focamos em:
- Padronizar a configuração de observabilidade e logs.
- Consolidar o ciclo de vida do FastAPI/queue como único ponto de entrada ativo.
- Preparar documentação que descreve a nova arquitetura modular.

## Arquitetura recomendada
1. **Entrada única**: o webhook FastAPI (`finbot.whatsapp.webhook`) coloca cada payload numa fila assíncrona, os workers (`finbot.core.conversation`) processam em paralelo limitado e responsivo.
2. **Domínio separado**: conversas, parsing e armazenamento vivem em camadas distintas (`core`, `services`, `database`) para evitar acoplamento.
3. **Integração com adaptador WhatsApp**: comunicamos com o Node/Baileys via `finbot/whatsapp/client.py`, mantendo o protocolo HTTP simples e com autenticação por API key.

## Fluxo de dados
1. WhatsApp envia payload para `/webhook`.
2. Validamos assinatura (secret), deduplicamos e enfileiramos a mensagem.
3. Worker consome fila, consulta/atualiza estado (`conversation_state`), chama NLP (fallback local + LLM) e dispara resposta.
4. Resposta é enviada pela camada de cliente (Baileys), e o banco registra a transação.

## Organização de código
- `finbot/core`: regras de conversa, config, observabilidade e máquinas de estado.
- `finbot/services`: domínios de AI (NLP, transcrição, relatórios, parser financeiro).
- `finbot/database`: conexão, modelos e repositórios.
- `finbot/whatsapp`: interface FastAPI/handlers/client integrando o adaptador Baileys.
- `finbot-baileys`: adaptador Node separado para manter a doorway para WhatsApp Web.

## Camadas do sistema
- **Interface**: FastAPI + queue em `webhook.py` para desacoplar entrada e processamento.
- **Processamento**: `conversation_manager` que orquestra intents, NLP e fallback.
- **Domínio**: repositórios e serviços financeiros para persistência/relatórios.
- **Infra**: config, logging estruturado, observabilidade e adaptação (Baileys, OLLAMA). 

## Tarefas implementadas nesta fase
- Criação do módulo `finbot.core.logging` que gera logs JSON e garante consistência para futuros eventos.
- Atualização do `main_api` para usar logging estruturado e manter a stack pronta para métricas.
- Documentação da fase (`docs/fase1-base-estrutural.md`) e registro no `implementation-log`.
- Ambiente local preparado (`.venv`, dependências instaladas) para testes rápidos sem afetar o sistema.
