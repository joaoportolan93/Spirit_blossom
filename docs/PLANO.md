# Plano de marcos

> Desenvolvedor solo. Simplicidade e reversibilidade pesam mais que sofisticação.

## Política de idioma e traduções

- **Código e arquitetura (ESTRITAMENTE EM INGLÊS)**: Todas as funções, métodos, classes, variáveis, models, tabelas, colunas, rotas e contratos da API devem ser escritos estritamente em inglês (`get_following_feed`, `content_text`, `author_id`, `created_at`, etc.).
- **Textos de UI e documentação**: Manter em português (pt-BR) neste momento. A tradução da interface para inglês é postergada para pós-MVP via arquivos de catálogo gettext (`.po` e `.mo`), sem dispersão de esforço agora.

## Política de faixa etária (18+ estrito)

- **Público exclusivo adulto**: A rede social é estritamente proibida para menores de 18 anos (`hard 18+ gate`).
- **Validação no backend**: Campo `birth_date` é obrigatório no registro (`RegisterSerializer`), rejeitando sumariamente usuários com idade inferior a 18 anos com erro 400.
- **Simplificação regulatória**: Elimina complexidade de conformidade com ECA Digital (Lei 14.811/2024), dispensando fluxos de consentimento parental e salvaguardas específicas para público infantojuvenil.

## Governança de agentes e modelos

- **Orquestrador principal**: Claude Sonnet 4.6 Thinking (coordena, sintetiza decisões, edita arquivos e roda testes).
- **Subagentes especialistas (E1 a E10)**: Operam obrigatoriamente no modelo **Gemini 3.8 Flash High** (`Model: flash`). Esse perfil de alta capacidade analítica é mandatório para análises técnicas, queries complexas e prevenção de falhas de segurança. Subagentes não alteram arquivos diretamente; entregam propostas analisadas para o orquestrador.

## Renomeações de modelo (Lumem → produto)

| Lumem (pt-BR) | Este projeto (EN) | Nota |
|---|---|---|
| `Usuario` | `User` | Model customizado de auth |
| `Perfil` | `UserProfile` | One-to-one com User |
| `Publicacao` | `Post` | |
| `Seguidor` | `Follow` | M2M via tabela intermediária |
| `RegistroConexao` | `AccessLog` | Marco Civil — validar com jurista |
| `Notificacao` | `Notification` | |
| `Comunidade` | `Community` | Feature flag — fora do M1 |
| `Bloqueio` | `Block` | |
| `Silenciamento` | `Mute` | |
| `Denuncia` | `Report` | |
| `DispositivoFCM` | `PushDevice` | VAPID (não FCM): campos `endpoint`, `p256dh`, `auth_key` |

## Renomeações de campo da API (Lumem → este projeto)

Executar o passo mecânico descrito em `apps/frontend/CONTEXT.md` no M1b.

| Campo antigo | Campo novo |
|---|---|
| `conteudo_texto` | `content_text` |
| `visibilidade` | `visibility` |
| `criado_em` | `created_at` |
| `autor` | `author` |
| `motivo` | `reason` (feed contract) |

---

## M0 — Fundações

**Objetivo:** estrutura de repositório, CI, ADRs, health checks.

- [x] README, .env.example, .gitignore
- [x] docker-compose.yml (Postgres pgvector, Redis, backend, worker, beat, frontend, nginx, feed stub)
- [x] Dockerfiles (backend Python 3.12, frontend Node→Nginx, feed Rust multi-stage)
- [x] infra/nginx/nginx.conf (X-Forwarded-Proto, X-Accel-Redirect)
- [x] config/settings.py (SECURE_PROXY_SSL_HEADER, JWT config, POST_MAX_CHARS)
- [x] config/urls.py + views.py (/api/health/)
- [x] config/celery.py (beat schedule com flush_expired_tokens)
- [x] services/feed/src/types.rs + main.rs (/health stub)
- [x] docs/api/feed-contract.json (JSON Schema neutro)
- [x] .github/workflows/ci.yml (backend/frontend/feed em matrix, E2E separado)
- [x] .pre-commit-config.yaml (Ruff, ESLint, cargo fmt)
- [x] CONTEXT.md em cada pasta de código
- [x] docs/adr/ADR-N1.md … ADR-N12.md
- [x] docs/PLANO.md (este arquivo)
- [x] docs/RISCOS.md

**Teste de staging CSRF (manual, não verificado automaticamente no M0):**
Ver `infra/CONTEXT.md`.

---

## M1a — Esqueleto backend

**Objetivo:** modelos, auth CSRF+JWT, endpoints base, ≥50 testes passando.

### Apps a criar

- `accounts`: `User`, `UserProfile`, `AccessLog`; `CookieJWTAuthentication`; views `/auth/*`
- `posts`: `Post`; search vector (spike Plan A → Plan B se falhar); seletor FTS
- `social`: `Follow`, `Block`, `Mute`; `get_visible_posts_queryset`
- `feed`: seletor chrono keyset; teste de contrato JSON Schema
- `notifications`: `Notification`

### Fluxo de CSRF detalhado

```
[Frontend] GET /api/auth/csrf/          → Django seta cookie csrftoken
[Frontend] POST /api/auth/login/        → lê cookie, manda X-CSRFToken header
                                           authentication_classes=[] nesta view
[Frontend] POST /api/posts/             → CookieJWTAuthentication chama _CSRFCheck
[Frontend] POST /api/auth/refresh/      → authentication_classes=[], _enforce_csrf() na view
[Frontend] POST /api/auth/logout/       → authentication_classes=[], _enforce_csrf() na view
```

### Spike do search_vector (primeiro passo do M1a)

1. Criar migration temporária com `GeneratedField(SearchVector(...), db_persist=True)`
2. Rodar `python manage.py makemigrations --check` e mostrar SQL gerado
3. Se gerar `GENERATED ALWAYS AS ... STORED` → **Plano A** (manter, apagar Plan B)
4. Se falhar → **Plano B**: `GinIndex` funcional + anotação `sv` no seletor (apagar Plan A)

### TokenRefreshView (correto)

```python
# authentication_classes = []  — access token pode estar expirado
# 1. Pegar refresh cookie
# 2. TokenRefreshSerializer(data={"refresh": token}).is_valid(raise_exception=True)
# 3. Ler serializer.validated_data["access"] e ["refresh"]
# 4. Verificar user.is_active e user.status válido
# 5. Setar cookies com max_age de settings, path="/api/auth/" para refresh
```

### Testes obrigatórios do M1a

| Grupo | Casos | Total |
|---|---|---|
| CSRF posts | POST sem token→403, com token→201, GET livre, DELETE→403 | 4 |
| CSRF refresh/logout | sem CSRF→403, com CSRF→200, cookie rotacionado | 3 |
| Refresh reutilizado | segundo uso do mesmo refresh→401 (rotação blacklist) | 1 |
| Refresh após logout | logout, tentar refresh→401 | 1 |
| Logout | cookie `access_token` presente com `max-age=0`, depois refresh→401 | 2 |
| Conta suspensa | refresh com user.is_active=False → 401 | 1 |
| Visibilidade | 10 casos (público, followers-only, bloqueio bidirecional) | 10 |
| Bid. block no feed | seguidor bloqueado não aparece, bloqueador não aparece | 6 |
| Feed + contrato | JSON Schema válido, cursor keyset, cursor inválido→400 | 8 |
| Auth | login ok, login senha errada, register, CSRF endpoint | 4 |
| Perfil | criar, editar, ver alheio | 3 |
| Follow | follow, unfollow, follow próprio→400 | 3 |
| AccessLog | criado no login, campo IP hasheado | 2 |
| **Total** | | **≥ 58** |

---

## M1b — Esqueleto frontend

**Objetivo:** páginas base, PWA, passo de renomeação de campos.

- Migrar sw.js manual → vite-plugin-pwa (Workbox)
- Axios com interceptor CSRF e withCredentials
- Páginas: Login, Register, Compose, Timeline (useInfiniteQuery), Profile
- Notificações: polling 30s
- Vitest: ≥11 testes (LoginForm 3, Composer 3, Timeline 3, FollowButton 2)
- Playwright E2E: cadastro→post→seguir→ver
- **Passo mecânico de renomeação**: ver `apps/frontend/CONTEXT.md`

---

## M2+ (referência)

- VAPID push nativo (sem FCM)
- Rate limiting granular por endpoint
- Communities (feature flag já no M1a)
- Moderação e denúncias

## M4 (referência)

- Algoritmo Rev3 ("Para Você")
- Embeddings MiniLM-L12-v2 (126 tokens úteis)
- Rust feed service com lógica real

