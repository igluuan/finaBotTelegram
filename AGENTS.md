# Repository Guidelines

## Project Structure & Module Organization
- `finbot/`: core Python application.
- `finbot/interfaces/telegram/`: Telegram entrypoints, handlers, and decorators.
- `finbot/interfaces/whatsapp/`: WhatsApp API/handler layer used by `main_api.py`.
- `finbot/services/`: business services (AI, parser, reports, scheduler).
- `finbot/database/`: SQLAlchemy models, connection, and repositories.
- `finbot-baileys/`: Node.js WhatsApp adapter (Baileys) exposing `/send-message`, `/status`, `/qr`.
- `tests/`: pytest suite (unit + integration-like tests by domain).
- Root scripts: `main.py` (Telegram bot) and `main_api.py` (WhatsApp FastAPI webhook).

## Build, Test, and Development Commands
- Install Python deps:
  - `pip install -r requirements.txt`
  - `pip install -r requirements-dev.txt`
- Run Telegram bot locally: `python main.py`
- Run WhatsApp API locally: `python main_api.py`
- Run Baileys adapter locally: `node finbot-baileys/server.js`
- Run tests: `PYTHONPATH=. pytest -q tests/`
- Run a focused test file: `PYTHONPATH=. pytest -q tests/test_parser_service.py`

## Coding Style & Naming Conventions
- Python: PEP 8, 4-space indentation, `snake_case` for functions/modules, `PascalCase` for classes.
- Keep handlers thin; place business logic in `services/` and data access in `database/repositories/`.
- Prefer explicit typing (`typing`) for public functions and async handlers.
- Node adapter (`finbot-baileys/`): keep endpoints minimal, validate inputs, and return clear HTTP status codes.

## Testing Guidelines
- Framework: `pytest` with `pytest-asyncio` and `pytest-mock`.
- Test files should be named `test_*.py`; mirror source domains (`tests/bot/handlers`, `tests/bot/services`, etc.).
- Add regression tests for bug fixes (especially webhook/auth, parser, and repository behaviors).

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
