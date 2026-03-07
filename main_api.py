import uvicorn
from finbot.core.logging import configure_structured_logging
from finbot.whatsapp.webhook import app
from finbot.database.connection import init_db


def main():
    configure_structured_logging()
    init_db()
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
