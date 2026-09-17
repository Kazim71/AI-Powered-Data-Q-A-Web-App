FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first, so code changes don't invalidate this layer.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app

# Run as non-root; sessions are written to a directory this user owns.
RUN useradd --create-home appuser \
    && mkdir -p /app/.sessions \
    && chown -R appuser /app
USER appuser

# Render/Railway inject $PORT; default to 8000 locally.
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
