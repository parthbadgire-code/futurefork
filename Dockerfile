# FutureFork backend image (FastAPI + OR-Tools CP-SAT + NumPy Monte Carlo)
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Application packages: API, engine, AI layer, ingestion + bundled sample CSVs, contracts
COPY backend/ /app/backend/
COPY engine/ /app/engine/
COPY ai/ /app/ai/
COPY data/ /app/data/
COPY contracts/ /app/contracts/

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD curl -f "http://localhost:${PORT}/health" || exit 1

# Shell form so $PORT (set by Render and other hosts) is honoured
CMD uvicorn backend.main:app --host 0.0.0.0 --port "${PORT}"
