import uvicorn
from finbot.whatsapp.webhook import app
from finbot.database.connection import init_db


def main():
    init_db()
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
