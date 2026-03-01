# ---- Frontend build stage ----
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# ---- Backend stage ----
FROM python:3.10-slim
WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc tesseract-ocr tesseract-ocr-rus poppler-utils && \
    rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY app/ app/
COPY agent/ agent/
COPY migrations/ migrations/
COPY alembic.ini .

# Frontend static files (built in previous stage)
COPY --from=frontend-build /app/frontend/dist /app/static

ENV PYTHONPATH=/app

# Entrypoint: run migrations then start server
RUN printf '#!/bin/sh\nset -e\nalembic upgrade head\nexec uvicorn app.main:app --host 0.0.0.0 --port 8000\n' > /app/entrypoint.sh \
    && chmod +x /app/entrypoint.sh

EXPOSE 8000

CMD ["/app/entrypoint.sh"]
