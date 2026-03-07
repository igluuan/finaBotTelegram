import os
from pathlib import Path
from dotenv import load_dotenv
from zoneinfo import ZoneInfo

# Adjusted paths for the new location (finbot/core/config.py)
# Root is ../../
ROOT_DIR = Path(__file__).parent.parent.parent
ENV_PATH = ROOT_DIR / ".env"

if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
AI_PROVIDER = os.getenv("AI_PROVIDER", "auto").lower()
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "phi3")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///finbot.db")
ALLOWED_USER_ID = os.getenv("ALLOWED_USER_ID")
WHATSAPP_WEBHOOK_SECRET = os.getenv("WHATSAPP_WEBHOOK_SECRET", "")
WHATSAPP_ADAPTER_API_KEY = os.getenv("WHATSAPP_ADAPTER_API_KEY", "")
WHATSAPP_ADAPTER_URL = os.getenv("WHATSAPP_ADAPTER_URL", "http://localhost:3000/send-message")
TIMEZONE = ZoneInfo("America/Sao_Paulo")
