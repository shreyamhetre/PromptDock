# PromptDock server + dashboard.
#   docker build -t promptdock .
#   docker run -p 8000:8000 -e DATABASE_URL=postgresql://... -e PROMPTDOCK_TOKEN=... promptdock
# Configure with DATABASE_URL (required) and PROMPTDOCK_TOKEN (optional, recommended: the
# container listens on 0.0.0.0, so without a token anyone who can reach it has access).

# 1. Build the dashboard (Node is only needed here, never at runtime).
FROM node:22-slim AS ui
WORKDIR /build/ui
COPY ui/package.json ui/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY ui/ ./
RUN npm run build

# 2. Build the wheel with the dashboard inside it.
FROM python:3.12-slim AS wheel
COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /bin/uv
WORKDIR /build
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY --from=ui /build/src/promptdock/ui/static ./src/promptdock/ui/static
RUN uv build --wheel --out-dir /dist

# 3. Runtime: just the installed package.
FROM python:3.12-slim
RUN useradd --create-home --uid 10001 promptdock
COPY --from=wheel /dist /tmp/dist
RUN pip install --no-cache-dir --timeout 120 --retries 5 "$(ls /tmp/dist/*.whl)[server,ui]" \
    && rm -rf /tmp/dist
USER promptdock
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"
CMD ["sh", "-c", "promptdock migrate && exec promptdock serve --ui --host 0.0.0.0 --port 8000"]
