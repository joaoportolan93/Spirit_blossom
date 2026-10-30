# Infraestrutura

Configuração de contêineres e proxy reverso.

## Componentes

| Serviço | Imagem | Nota |
|---|---|---|
| `db` | `pgvector/pgvector:pg16` | PostgreSQL 16 + pgvector |
| `redis` | `redis:7-alpine` | Broker Celery + cache |
| `backend` | build local | Django + Gunicorn |
| `worker` | build local (backend) | Celery worker |
| `beat` | build local (backend) | Celery beat scheduler |
| `frontend` | build local | React → Nginx |
| `nginx` | `nginx:1.27-alpine` | Proxy reverso |
| `feed` | build local (perfil `feed`) | Rust stub — Fase 1+ |

## Perfis

- **Padrão** (`docker compose up`): sobe tudo exceto `feed`.
- **Com feed**: `docker compose --profile feed up`.

## Proxy CSRF em produção

O Nginx repassa `X-Forwarded-Proto` e `Host` ao backend.
O Django usa `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")`.
`CSRF_TRUSTED_ORIGINS` deve incluir a origem com `https://` em produção.

**Teste em staging (manual):**
1. Fazer POST em `/api/auth/csrf/` → obter `csrftoken` no cookie.
2. Fazer POST em `/api/posts/` com `X-CSRFToken` correto → esperar 201.
3. Fazer POST sem `X-CSRFToken` → esperar 403.
