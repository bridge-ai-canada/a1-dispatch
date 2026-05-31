# A1 Field Pro — Backend (FastAPI + Motor)
# Multi-stage build for slim production image.

# ----- Build stage -----
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

# System deps required to compile bcrypt / cryptography wheels for non-x86 hosts
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential gcc curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --prefix=/install --no-cache-dir -r requirements.txt && \
    pip install --prefix=/install --no-cache-dir \
        --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/ \
        emergentintegrations || true

# ----- Runtime stage -----
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8001

# Run as non-root for SOC2 / least-privilege
RUN useradd -m -u 10001 -s /bin/bash app && \
    apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates tini \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

WORKDIR /app/backend
COPY --chown=app:app . /app/backend

USER app

EXPOSE 8001

HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:8001/api/health || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "4", "--proxy-headers", "--forwarded-allow-ips", "*"]
