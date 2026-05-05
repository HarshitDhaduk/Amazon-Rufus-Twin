# ── Stage 1: Build ─────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies (needed for chromadb native extensions)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies into a prefix dir (for clean copy to runtime)
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --prefix=/install --no-cache-dir -r requirements.txt


# ── Stage 2: Runtime ────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY . .

# Create the ChromaDB data directory (ephemeral on Cloud Run — warm instances keep it alive)
RUN mkdir -p /app/data/chroma_db

# Cloud Run injects PORT env var. Default to 8000 for local dev.
ENV PORT=8000
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Run uvicorn. Use $PORT for Cloud Run compatibility.
CMD uvicorn main:app \
    --host 0.0.0.0 \
    --port $PORT \
    --workers 1 \
    --timeout-keep-alive 3600 \
    --log-level info
