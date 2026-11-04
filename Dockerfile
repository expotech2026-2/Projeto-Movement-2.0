# Etapa 1: build do frontend React.
FROM node:24-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Etapa 2: FastAPI servindo a API em /api e o build do frontend na raiz.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app/backend
COPY backend/requirements.lock ./
RUN pip install -r requirements.lock
COPY backend/ ./
COPY --from=web /web/dist /app/frontend/dist
RUN useradd --system --uid 10001 movement
USER movement
EXPOSE 8000
# Aplica migrações pendentes antes de aceitar conexões.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.site:create_site --factory --host 0.0.0.0 --port 8000"]
