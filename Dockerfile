FROM python:3.11-slim

ARG PIP_INDEX_URL=https://pypi.org/simple

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/app/data \
    PORT=8000

WORKDIR /app

COPY requirements.lock .
RUN pip install --index-url "${PIP_INDEX_URL}" -r requirements.lock

COPY app/ /app/app/
COPY entrypoint.sh /app/entrypoint.sh

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /app app \
    && mkdir -p /app/data \
    && chown -R app:app /app \
    && chmod +x /app/entrypoint.sh

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"

ENTRYPOINT ["/app/entrypoint.sh"]
