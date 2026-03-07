# Ollama como provedor principal

Este projeto agora prioriza o Ollama para gerar prompts e respostas (dicas, confirmações, relatórios, transcrições). O módulo `finbot.services.ai_service` já foi alinhado para:

- tentar o Ollama primeiro (`AI_PROVIDER=auto`, valor padrão);
- só recorrer ao Gemini se o Ollama não responder.

## Passos rápidos
1. Instale o Ollama local e baixe o modelo preferido (exemplo leve):
   ```bash
   ollama pull phi3-mini
   ```
2. Inicie o servidor para que o backend consiga chamá-lo:
   ```bash
   ollama serve --listen 0.0.0.0:11434
   ```
3. Ajuste as variáveis no `.env` ou no `docker-compose.yml`:
   ```ini
   AI_PROVIDER=auto
   OLLAMA_BASE_URL=http://host.docker.internal:11434
   OLLAMA_MODEL=phi3-mini
   ```
   * No ambiente local fora do Docker, `http://localhost:11434` também funciona.
   * No Docker Compose, `host.docker.internal` permite que o container Python alcance o host que roda o Ollama.

## Verificação
- Use `curl` no host que roda o Ollama para garantir que o endpoint responde:
  ```bash
  curl -X POST http://localhost:11434/api/generate \
    -H "Content-Type: application/json" \
    -d '{"model":"phi3-mini","prompt":"Ola"}'
  ```
- Observe os logs estruturados (`finbot.core.logging`): mensagens como “Error calling Ollama” indicam tentativas e falhas.

## Considerações
- O padrão `AI_PROVIDER=auto` garante resiliência: Ollama segue prioritário e Gemini entra só se o primeiro falhar.
- Escolha um modelo compatível com a RAM da VPS; `phi3-mini` ou `mistral-7b-instruct` são bons candidatos para uso pessoal.
- Se quiser forçar apenas o Ollama, defina `AI_PROVIDER=ollama`, mas garanta que o servidor esteja no ar antes de subir o backend.
