# Social Network — Repositório

> Documentação de uso e variáveis de ambiente. Nomes de produto são configuráveis via env.

## Pré-requisitos

- Docker ≥ 26 e Docker Compose v2
- Python 3.12 (desenvolvimento local)
- Node.js 20 LTS (desenvolvimento local)
- Rust 1.77+ (apenas `services/feed/`)

## Variáveis de ambiente

Copie `.env.example` para `.env` e preencha os valores:

```bash
cp .env.example .env
```

Variáveis obrigatórias — consulte `.env.example` para a lista completa.

| Variável | Descrição |
|---|---|
| `APP_NAME` | Nome exibido na UI e e-mails |
| `SECRET_KEY` | Chave Django — gere com `python -m django generate-secret-key` |
| `POSTGRES_PASSWORD` | Senha do banco de dados |
| `REDIS_PASSWORD` | Senha do Redis |
| `BACKEND_PORT` | Porta exposta pelo Nginx (padrão: 8000) |
| `VITE_APP_NAME` | Nome exibido no frontend (igual a APP_NAME) |
| `CORS_ALLOWED_ORIGINS` | Origens permitidas separadas por vírgula |
| `CSRF_TRUSTED_ORIGINS` | Origens confiáveis para CSRF separadas por vírgula |

## Comandos principais

```bash
# Subir infra básica (Postgres + Redis)
docker compose up -d db redis

# Subir tudo
docker compose up -d

# Migrations
docker compose exec backend python manage.py migrate

# Testes backend
docker compose exec backend python -m pytest -v

# Testes frontend
docker compose exec frontend npm test

# Analisar código Rust
docker compose run --rm feed cargo clippy

# Formatar código
pre-commit run --all-files
```

## Estrutura de diretórios

```
apps/
  backend/     Django + DRF + Celery
  frontend/    React + Vite + PWA
services/
  feed/        Rust (Axum) — stub M0, lógica a partir da Fase 1
infra/
  nginx/       Configuração Nginx
docs/
  adr/         Architecture Decision Records
  api/         Contratos de API (JSON Schema / OpenAPI)
```

## Marcos

| Marco | Descrição |
|---|---|
| M0 | Fundações — estrutura, CI, ADRs, health checks |
| M1a | Esqueleto backend — modelos, auth, feed seguindo |
| M1b | Esqueleto frontend — páginas base, PWA |
| M2+ | Features incrementais |
