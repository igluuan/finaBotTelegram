FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DATABASE_URL=sqlite:////tmp/finbot.db

COPY finbot/requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir --upgrade pip && \
    python -m pip install --no-cache-dir -r requirements.txt

COPY finbot ./finbot

RUN adduser --disabled-password --no-create-home botuser
USER botuser

CMD ["python", "-m", "finbot.main"]
