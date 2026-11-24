# The fleet hub: the web UI (built here) plus the Python server.
# Build from the repo root:  docker build -f hub/Dockerfile -t fleet-telemetry-hub .
# deploy/docker-compose.yml does this for you.

FROM node:24-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm install --no-audit --no-fund
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/hub:/app/shared \
    HUB_BIND=0.0.0.0 \
    HUB_DATA_DIR=/data \
    HUB_WEB_DIR=/app/web
WORKDIR /app

# Dependencies pinned by uv.lock (the same versions the tests ran with).
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv==0.9.25 \
    && uv export --frozen --no-dev --no-emit-project --no-hashes -o /tmp/requirements.txt \
    && pip install --no-cache-dir -r /tmp/requirements.txt \
    && pip uninstall -y uv && rm /tmp/requirements.txt

COPY shared/ shared/
COPY hub/fleet_hub/ hub/fleet_hub/
COPY --from=web /web/dist/ web/

RUN useradd --system --uid 10001 hub && mkdir -p /data && chown hub /data
USER hub
VOLUME /data
EXPOSE 8100 8101

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8100/api/health', timeout=4)"

CMD ["python", "-m", "fleet_hub"]
