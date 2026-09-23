FROM python:3.12.14-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install --no-install-recommends --yes aria2 ca-certificates ffmpeg tzdata \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 10001 bot

WORKDIR /app
COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir --requirement requirements.lock

COPY --chown=bot:bot . .
RUN mkdir --parents /data/backups && chown --recursive bot:bot /data

USER bot

CMD ["python", "main.py"]
