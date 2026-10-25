# ─── Builder stage ──────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ─── Runtime stage ──────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH
ENV HOME=/root
# Do not bake secrets into the image — pass via compose/K8s/EC2 env at runtime.
ENV PYTHONUNBUFFERED=1

COPY . .

RUN adduser --disabled-password --gecos "" appuser \
    && chown -R appuser:appuser /app /root/.local \
    && chmod 755 /root \
    && chmod +x /app/entrypoint.sh
USER appuser

EXPOSE 8000

# Readiness (DB) — matches ALB target-group check you will use on AWS
HEALTHCHECK --interval=15s --timeout=5s --start-period=40s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=3)"

ENTRYPOINT ["/app/entrypoint.sh"]
