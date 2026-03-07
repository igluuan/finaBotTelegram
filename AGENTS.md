# Repository Guidelines

## Project Structure & Module Organization
- `finbot/`: core Python application.
- `finbot/whatsapp/`: active WhatsApp API, webhook, schemas, and client used by `main_api.py`.
- `finbot/interfaces/whatsapp/`: compatibility wrappers that re-export the active WhatsApp modules.
- `finbot/interfaces/telegram/` and `finbot/bot/`: legacy Telegram code kept only for historical reference and slated for removal.
- `finbot/services/`: business services (AI, parser, reports, scheduler).
- `finbot/database/`: SQLAlchemy models, connection, and repositories.
- `finbot-baileys/`: Node.js WhatsApp adapter (Baileys) exposing `/send-message`, `/status`, `/qr`.
- `tests/`: pytest suite (unit + integration-like tests by domain).
- Root scripts: `main.py` and `main_api.py` both start the WhatsApp FastAPI webhook.

## Build, Test, and Development Commands
- Install Python deps:
  - `pip install -r requirements.txt`
  - `pip install -r requirements-dev.txt`
- Run WhatsApp API locally: `python main_api.py`
- `python main.py` is an alias to the same WhatsApp runtime.
- Run Baileys adapter locally: `node finbot-baileys/server.js`
- Run tests: `PYTHONPATH=. pytest -q tests/`
- Run a focused test file: `PYTHONPATH=. pytest -q tests/whatsapp/test_whatsapp.py`
- The active runtime should not depend on `python-telegram-bot`.

## Coding Style & Naming Conventions
- Python: PEP 8, 4-space indentation, `snake_case` for functions/modules, `PascalCase` for classes.
- Keep channel handlers thin; place business logic in `services/` and data access in `database/repositories/`.
- Prefer explicit typing (`typing`) for public functions and async handlers.
- Node adapter (`finbot-baileys/`): keep endpoints minimal, validate inputs, and return clear HTTP status codes.

## Testing Guidelines
- Framework: `pytest` with `pytest-asyncio` and `pytest-mock`.
- Test files should be named `test_*.py`; mirror source domains.
- Add regression tests for bug fixes, especially webhook/auth, parser, and repository behaviors.

## Commit & Pull Request Guidelines
- Follow short, imperative commit messages with prefixes seen in history: `feat:`, `fix:`, `refactor:`, `chore:`.
- Keep commits scoped (one concern per commit).
- PRs should include:
  - objective and impact,
  - changed modules/paths,
  - test evidence (`pytest` output or targeted checks),
  - config/environment changes (if any).

## Security & Configuration Tips
- Never commit real secrets in `.env` (Telegram token, API keys, webhook secrets).
- Use `WHATSAPP_ADAPTER_API_KEY` and `WHATSAPP_WEBHOOK_SECRET` consistently between Python and Node services.
- Mask personal data (phone/message content) in logs whenever possible.
