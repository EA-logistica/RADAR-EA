FROM node:24-bookworm-slim AS web
WORKDIR /build
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.14-slim-bookworm
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock && python -m playwright install --with-deps chromium
COPY radar/ radar/
COPY migrations/ migrations/
COPY alembic.ini pyproject.toml ./
COPY --from=web /build/dist web/dist
RUN mkdir -p /app/data/raw && useradd -m -u 10001 radar && chown -R radar:radar /app/data /ms-playwright
USER radar
EXPOSE 8000
CMD ["python","-m","uvicorn","radar.api:app","--host","0.0.0.0","--port","8000"]
