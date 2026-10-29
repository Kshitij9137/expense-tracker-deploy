# ---- Expense Tracker production image ----
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    APP_ENV=production \
    DB_PATH=/data/expenses.db \
    PORT=8000 \
    WEB_CONCURRENCY=2

WORKDIR /app

# Run as a non-root user (security hardening) and prepare the data directory.
RUN useradd --create-home --uid 10001 appuser \
 && mkdir -p /data && chown appuser:appuser /data

# Install dependencies first so Docker can cache this layer.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY scripts ./scripts

USER appuser
VOLUME ["/data"]
EXPOSE 8000

# Docker marks the container unhealthy if /health stops answering.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT','8000'), timeout=3)"

# API_KEY must be supplied at run time (never baked into the image).
CMD ["sh", "-c", "exec gunicorn expense_tracker.wsgi:app --bind 0.0.0.0:${PORT} --workers ${WEB_CONCURRENCY} --timeout 30 --graceful-timeout 20"]
