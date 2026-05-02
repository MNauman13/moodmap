# STAGE 1: Builder
# Build context must be the project root (.) so we can copy backend/ as a package.
# This lets `from backend.X import ...` resolve correctly inside the container.
FROM python:3.11-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /build/wheels -r requirements.txt


# STAGE 2: Runner
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    curl \
    libsndfile1 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN addgroup --system appgroup && adduser --system --group appuser

COPY --from=builder /build/wheels /wheels
COPY --from=builder /build/requirements.txt .
RUN pip install --no-cache /wheels/*

# Copy backend as a package so `from backend.X import ...` resolves at /app/backend/
COPY backend/ ./backend/

RUN chown -R appuser:appgroup /app
USER appuser

EXPOSE 8000
# Production-tuned Uvicorn:
#   --loop uvloop      faster async event loop (Linux C extension, ~2x throughput)
#   --http httptools   faster HTTP parser (C extension)
#   --workers 4        pinned for predictable container memory; tune via WORKERS env if needed
CMD ["uvicorn", "backend.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "4", \
     "--loop", "uvloop", \
     "--http", "httptools", \
     "--worker-connections", "1000"]
