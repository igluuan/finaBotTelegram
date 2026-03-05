import os
from pathlib import Path
from dotenv import load_dotenv

_env_path_local = Path(__file__).parent / ".env"
_env_path_root = Path(__file__).parent.parent / ".env"
if _env_path_root.exists():
    load_dotenv(dotenv_path=_env_path_root)
if _env_path_local.exists():
    load_dotenv(dotenv_path=_env_path_local)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///finbot.db")
ALLOWED_USER_ID = os.getenv("ALLOWED_USER_ID")
