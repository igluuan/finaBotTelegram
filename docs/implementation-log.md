# Implementation Log

## 2026-03-07

### Phase 1 - WhatsApp-only runtime
- Removed Telegram from the active runtime path.
- Changed `docker-compose.yml` so the Python container starts only `main_api.py`.
- Turned `main.py` into an alias for the WhatsApp API entrypoint to avoid old Telegram boot behavior.
- Consolidated duplicated WhatsApp interface modules into compatibility wrappers around `finbot.whatsapp.*`.
- Updated `AGENTS.md` to reflect the WhatsApp-first runtime.

Validation performed:
- `docker compose config`
- Python syntax check of the modified files
- Recreated the `bot` container and confirmed Uvicorn boot on port `8000`

Rationale:
- The project is personal and currently serves at most two users.
- Reducing moving parts is more important than preserving multi-channel flexibility.
- WhatsApp is now the only active channel, so Telegram should not remain in the boot path.

### Phase 2 - Conversation flow hardening
Current goal:
- Improve daily usability for short WhatsApp messages.
- Make the bot more reliable when the LLM is unavailable or partially wrong.

Focus areas:
- missing field questions
- correction flow during confirmation
- short help responses
- deterministic fallback parsing for common finance phrases

Implemented:
- Added deterministic fallback understanding for income, installment and expense phrases without relying entirely on the LLM.
- Improved the conversation manager to ask only for the next missing field:
  - amount
  - category
  - installment count
- Added short correction handling during confirmation, such as:
  - `foi 52`
  - `categoria mercado`
  - `3x`
- Shortened confirmation copy for WhatsApp usability.
- Added a first regression test file for the conversation manager.

Validation performed:
- Python syntax check of the changed modules
- Rebuilt and restarted the Python backend container
- Confirmed boot logs from Uvicorn
- Confirmed `GET /health` returns `{"ok": true, "queue_size": 0, "workers": 2}`
- Ran `python -m pytest -q tests/test_conversation_manager.py tests/whatsapp/test_whatsapp.py` inside the backend container: `8 passed`

Pending validation:
- none for this round

### Phase 2.1 - FastAPI lifecycle cleanup
Implemented:
- Replaced deprecated FastAPI `on_event` hooks in `finbot/whatsapp/webhook.py` with a `lifespan` handler.

Validation performed:
- Python syntax check of the webhook module
- Rebuilt and restarted the Python backend container
- Confirmed `GET /health` still returns `{"ok": true, "queue_size": 0, "workers": 2}`
- Re-ran `python -m pytest -q tests/test_conversation_manager.py tests/whatsapp/test_whatsapp.py` inside the backend container: `8 passed`

### Phase 2.2 - Telegram runtime dependency cleanup
Implemented:
- Removed `python-telegram-bot` from the active Python dependency lists.
- Updated repository guidance to make it explicit that Telegram code is legacy only and should not be part of the active runtime.
- Excluded legacy Telegram code and tests from the Docker build context in `.dockerignore`.

Rationale:
- The runtime is now WhatsApp-only.
- Keeping Telegram as an installed dependency increases image weight and maintenance with no current value.
- Keeping Telegram source in the runtime build context also adds noise and slows rebuilds without adding value.

Pending follow-up:
- Remove or archive legacy Telegram source and tests in a dedicated cleanup round.

Validation performed:
- Python syntax check of active WhatsApp modules
- Rebuilt and restarted the backend image without `python-telegram-bot`
- Confirmed `GET /health` still returns `{"ok": true, "queue_size": 0, "workers": 2}`
- Re-ran `python -m pytest -q tests/test_conversation_manager.py tests/whatsapp/test_whatsapp.py` inside the backend container: `8 passed`

### Phase 2.3 - Natural queries by category and period
Implemented:
- Improved local intent fallback to detect balance/report queries with category and period.
- Added `ReportService.get_category_period_report(...)`.
- Updated the WhatsApp report path so structured report intents can answer queries like:
  - `quanto gastei com mercado essa semana`
- Extended the same path to detect income queries like:
  - `quanto recebi esse mês`

Goal:
- Make day-to-day queries work naturally in WhatsApp without commands or manual filtering.

Validation performed:
- Python syntax check of the changed modules
- Rebuilt and restarted the backend container
- Confirmed `GET /health` still returns `{"ok": true, "queue_size": 0, "workers": 2}`
- Ran `python -m pytest -q tests/test_conversation_manager.py tests/whatsapp/test_whatsapp.py tests/whatsapp/test_reporting.py` inside the backend container: `12 passed`

### Phase 3.0 - Audio ingestion groundwork
Implemented:
- Extended the Baileys adapter to detect incoming audio messages and forward audio metadata to the backend.
- Added audio fields to the WhatsApp webhook schema:
  - `media_type`
  - `mime_type`
  - `media_base64`
  - `file_length`
  - `voice_note`
- Added an initial audio service stub in the backend.
- The backend now answers explicitly when it receives an audio message instead of silently ignoring it.

Current behavior:
- Audio is accepted end-to-end.
- The backend responds that transcription is not enabled yet and asks for text as a temporary fallback.

Rationale:
- This opens the audio pipeline safely without pretending transcription already exists.
- It is better for daily usability to acknowledge voice messages than to ignore them.

Validation performed:
- Python syntax check of the changed Python modules
- Rebuilt and restarted the full stack
- Confirmed `GET /health` still returns `{"ok": true, "queue_size": 0, "workers": 2}`
- Ran `python -m pytest -q tests/test_conversation_manager.py tests/whatsapp/test_whatsapp.py tests/whatsapp/test_reporting.py tests/whatsapp/test_audio.py` inside the backend container: `14 passed`
- Added file persistence for uploaded audio and wound the pipeline toward transcription.

### 2026-03-07 - Fase 1 estruturada (documentação e observabilidade)
Implementado:
- Criado `.venv` local e instalado `requirements.txt` para isolar dependências enquanto o desenvolvimento acontece fora do sistema base.
- Introduzido `finbot.core.logging` para emitir logs em JSON e facilitar rastreabilidade sem sacrificar a simplicidade do projeto pessoal.
- Atualizado `main_api.py` para usar logging estruturado antes de iniciar o FastAPI/Uvicorn.
- Documentada a fase 1 em `docs/fase1-base-estrutural.md`, alinhando arquitetura, fluxo e camadas ao foco atual no WhatsApp.
- Confirmado que os containers Docker (`finbot_python`, `finbot_whatsapp`) continuam rodando na mesma stack.
Validação:
- Logs manuais e inspeção de `docker compose ps` para garantir as duas peças principais estão ativas.

### 2026-03-07 - Ollama como principal provedor
Implementado:
- Mudança do comportamento padrão de `AI_PROVIDER` para `auto`, priorizando o Ollama e permitindo fallback para o Gemini.
- Documentação nova em `docs/ollama-setup.md` para descrever instalação, execução e variáveis necessárias ao Ollama.
Validação:
- Revisão manual do fluxo `ai_service.generate_content` e verificação de que o fallback acontece quando o Ollama não responde.
