import uvicorn
from finbot.whatsapp.webhook import app
from finbot.bot.database import crud

def main():
    crud.init_db()
    # Inicia o servidor uvicorn
    # Em produção, use: uvicorn finbot.main_api:app --host 0.0.0.0 --port 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()
