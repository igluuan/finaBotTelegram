import os
from pathlib import Path
from dotenv import load_dotenv

# Garante carregamento do .env localizado no mesmo diretório deste arquivo,
# independentemente do diretório corrente ao executar o script.
_env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=_env_path)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///finbot.db")
ALLOWED_USER_ID = os.getenv("ALLOWED_USER_ID")

# Validação adiada: não falha no import se variáveis faltarem.
# Os pontos que exigem essas variáveis (ex.: inicialização do bot/IA) devem validá-las.
