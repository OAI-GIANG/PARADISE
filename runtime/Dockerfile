FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PARADISE_HOST=0.0.0.0 \
    PARADISE_PORT=8787 \
    PARADISE_DATA=/data/paradise.sqlite3

WORKDIR /app
COPY paradise /app/paradise

RUN useradd --create-home --uid 10001 paradise \
    && mkdir -p /data \
    && chown -R paradise:paradise /app /data

USER paradise
EXPOSE 8787

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8787/healthz', timeout=3).read()"

CMD ["python", "-m", "paradise.server"]
