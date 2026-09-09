# syntax=docker/dockerfile:1
#
# GP — FastAPI BFF + React UI. Build context = this repo root.
#   docker compose up -d --build

# ---- Stage 1: build the React/Vite frontend ----
FROM node:20-slim AS frontend
WORKDIR /frontend
COPY frontend/ ./
RUN rm -f package-lock.json \
    && npm install --no-audit --no-fund
RUN --mount=type=cache,target=/root/.npm \
    npm run build

# ---- Stage 2: Python runtime ----
FROM python:3.13-slim-bookworm AS builder
ENV PYTHONIOENCODING=UTF-8 LANG=C.UTF-8 LC_ALL=C.UTF-8
WORKDIR /app
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip setuptools wheel && \
    pip install \
    "fastapi>=0.110" "uvicorn>=0.27" \
    "pydantic>=2.5.0" "requests>=2.31.0" "httpx>=0.27" \
    "openai>=1.40" "anthropic>=0.40.0"

FROM python:3.13-slim-bookworm
ENV TERM=xterm
WORKDIR /app
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates

COPY --from=builder /usr/local/lib/python3.13/site-packages/ /usr/local/lib/python3.13/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

COPY src/ ./src/
COPY run_server.py ./
COPY --from=frontend /frontend/dist ./frontend/dist

RUN find . -name "*.py" -exec sed -i 's/\r$//' {} \;

RUN echo "Verifying app imports..." && \
    test -f frontend/dist/index.html && \
    PYTHONPATH=/app python -c "import src.app; print('src.app imported OK')" && \
    echo "All verifications passed!"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    APP_PORT=8069 \
    MEDIA_DIR=/media

EXPOSE 8069
CMD ["sh", "-c", "uvicorn src.app:api --host 0.0.0.0 --port ${APP_PORT:-8069} --log-level info"]
