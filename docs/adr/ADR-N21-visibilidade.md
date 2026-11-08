# ADR-N21 — Módulo central de visibilidade (Onda 3a)

**Status:** Aceito  
**Data:** 2026-11-06  
**Decisores:** Orquestrador (ToT para decisões de conta privada e círculo)  
**Referência:** Estudo do Lumem (`docs/lumem-study/01-privacidade-e-vazamentos.md`), Auditoria do fork (`docs/lumem-study/02-auditoria-do-fork.md`)

---

## Contexto

A auditoria A2 identificou 3 falhas de visibilidade no fork:

1. `search_posts` sem filtro de visibilidade ou bloqueio (crítica)
2. `ProfileDetailView` lista posts sem chamar o seletor central
3. `get_profile_counters` conta sem checar bloqueio

Além disso, faltam: conta privada, círculo de amigos no seletor, can_view_post, can_view_profile.

---

## Tree of Thoughts — Conta privada (campo)

| Critério | Peso | Em User diretamente | Em UserProfile | Campo separado PrivacySettings |
|---|---|---|---|---|
| Simplicidade | ×3 | 4 | 5 | 2 |
| Segurança/Privacidade | ×3 | 4 | 4 | 4 |
| Reversibilidade | ×2 | 3 | 5 | 3 |
| Cabe no ARM sem GPU | ×2 | 5 | 5 | 4 |
| Esforço | ×2 | 3 | 5 | 1 |
| Não predatório | ×2 | 5 | 5 | 5 |
| **Total** | | **50** | **58** | **38** |

> Nota: Segurança de UserProfile = 4 (não 5): migration em tabela menor, mas perfil pode estar ausente se não foi criado. Mitigação: `get_or_create` no signal de registro. Não elimina o ramo.

**Vencedor: Em `UserProfile`** — menor tabela, semanticamente correto, reversível com alter column.

**Trade-off declarado:** Se `UserProfile` não existir para um usuário (bug de criação de conta), `is_private` lança `RelatedObjectDoesNotExist`. Mitigação: `can_view_profile` trata a ausência como conta pública (posição menos restritiva aceitável aqui pois a ausência de perfil = conta não configurada).

---

## Decisão

### 1. Novos campos de modelo

**`UserProfile.is_private`** (BooleanField, default=False):
- `True` → conta privada: só seguidores ativos veem posts e perfil completo
- Conta privada: não-seguidor vê apenas username, display_name, avatar e botão Seguir (sem bio, contadores, posts)

**`Post.Visibility.CIRCLE = "circle"`**:
- Acrescentar ao TextChoices existente
- Posts de círculo são visíveis apenas para `Follow(follower=viewer, followed=author, is_close_friend=True, status="active")`

**`Follow.status`** (CharField, choices `active`/`pending`, default=`active`):
- `active`: follow aprovado
- `pending`: aguarda aprovação de conta privada
- Migration: campo com default=`active` preserva todos os follows existentes

### 2. API do módulo central (`social/selectors.py`)

```python
def can_view_post(viewer, post) -> bool:
    """Retorna True se viewer pode ver o post. Nunca levanta exceção."""

def visible_posts_for(viewer) -> QuerySet:
    """QuerySet base de Posts visíveis para viewer. Substitui get_visible_posts_queryset."""

def can_view_profile(viewer, target) -> bool:
    """True se viewer pode ver perfil completo de target (não-anon, não-bloqueado, segue se privado)."""
```

`visible_posts_for` respeita, em ordem:
1. Bloqueio bidirecional → exclui
2. Visibilidade do post:
   - `PUBLIC`: visível para todos (autenticados e anônimos)
   - `FOLLOWERS`: só followers ativos do autor + o próprio autor
   - `CIRCLE`: só `is_close_friend=True` followers ativos + o próprio autor
3. Conta privada do autor: mesma lógica (follower ativo vê; pendente/não-seguidor não vê)

**`can_view_post`** é derivado de `visible_posts_for` para manter consistência (não duplicar lógica).

**Semântica de recurso inacessível:** sempre 404, nunca 403.

### 3. Comportamentos de borda

| Situação | Comportamento |
|----------|---------------|
| Remover do círculo (`is_close_friend = False`) | Posts de círculo somem imediatamente do feed/perfil do ex-membro |
| Deixar de seguir | Follow deletado → posts de círculo e followers somem imediatamente |
| Bloquear | Follow deletado em ambas as direções → posts invisíveis imediatamente |
| Mudar visibilidade de post depois de publicado | Aplica imediatamente (sem cache) |
| Post de círculo + menção | Notificação só é criada se destinatário tiver `can_view_post == True` |
| Post de círculo + curtida | Curtida só é possível se `can_view_post == True` |
| Viewer = autor | Sempre pode ver o próprio post (incluindo privado e rascunho) |

### 4. Conta privada — o que cada relação vê em `GET /api/social/profile/<username>/`

Reconciliação: contas bloqueadas retornam `404 Not Found` (fail-closed, sem expor existência). Contas privadas para não-seguidores/pendentes retornam `200 OK` com payload mínimo para permitir solicitar ou visualizar o status de seguir.

| Relação | HTTP Status | Bio | Contadores | Posts | Status de Seguir |
|---|---|---|---|---|---|
| Bloqueado mútuo (em qualquer direção) | `404 Not Found` | Oculto | Oculto | Oculto | Oculto |
| Não seguidor de conta privada | `200 OK` | `""` (vazio) | Zerados (0/0/0) | `[]` (vazio) | `is_following=false`, `follow_status=null` |
| Seguidor pendente de conta privada | `200 OK` | `""` (vazio) | Zerados (0/0/0) | `[]` (vazio) | `is_following=false`, `follow_status="pending"` |
| Seguidor ativo de conta privada | `200 OK` | Completa | Reais | Públicos + Followers | `is_following=true`, `follow_status="active"` |
| Amigo próximo (círculo) | `200 OK` | Completa | Reais | Públicos + Followers + Circle | `is_following=true`, `is_close_friend=true` |
| O próprio dono | `200 OK` | Completa | Reais | Todos (incl. privados/drafts) | `is_following=false`, `follow_status=null` |

#### Rota Padronizada de Configuração de Privacidade (Onda 5)

- **Caminho padronizado**: `PATCH /api/users/profile/`
- **Permissão**: `IsAuthenticated` (apenas o próprio usuário pode alterar seu perfil)
- **Payload**: `{ "is_private": true }` ou `{ "is_private": false }`
- **Efeito**: Alterna `UserProfile.is_private`. Novos pedidos de seguir tornam-se `pending` quando `is_private=true`.

### 5. Regras de busca e Explorar

**Busca de usuários** (`GET /api/users/search/?q=`):
- Prefixo de username, mínimo 2 caracteres, limite 20
- Exclui bloqueados em ambas as direções
- Nunca busca por e-mail
- Throttle: 30/min por usuário

**Explorar** (`GET /api/feed/explore/`):
- Apenas posts públicos (`visibility=PUBLIC`)
- Exclui posts de autores que o viewer bloqueou ou que bloquearam o viewer
- Exclui posts de autores que o viewer silenciou
- Ordenação cronológica por keyset (campo `id` DESC)
- `reason: "explore"` no contrato do feed

### 6. Contratos de endpoint (publicados antes de liberar subagentes)

```
POST   /api/social/close-friends/{username}/
DELETE /api/social/close-friends/{username}/
GET    /api/social/close-friends/
GET    /api/users/search/?q={prefix}&limit={int}
GET    /api/feed/explore/?cursor={uuid}
```

#### `POST /api/social/close-friends/{username}/`
```json
{ "detail": "Adicionado ao círculo." }
// 201 Created — ou 400 se não segue / já está no círculo
// 404 se username não existe
```

#### `DELETE /api/social/close-friends/{username}/`
```json
{ "detail": "Removido do círculo." }
// 204 No Content — ou 404 se não estava no círculo
```

#### `GET /api/social/close-friends/`
```json
{
  "results": [
    { "username": "alice", "avatar": "...", "follow_since": "2026-11-01T..." }
  ]
}
```

#### `GET /api/users/search/?q=ali&limit=20`
```json
{
  "results": [
    { "username": "alice", "avatar": "...", "is_private": false, "follow_status": "active" }
  ]
}
```

#### `GET /api/feed/explore/?cursor={uuid}`
```json
{
  "items": [
    { "post_id": "...", "reason": "explore", "cursor": "..." }
  ],
  "next_cursor": "..." | null
}
```

---

## Consequências

**Positivas:**
- Toda listagem de posts passa por `visible_posts_for` — gate arquitetural testável
- 3 falhas existentes corrigidas em T1
- Nenhuma dependência nova

**Negativas / trade-offs:**
- Migration adiciona `Follow.status` e `UserProfile.is_private` — reversível com alter column
- `can_view_post` é O(1) em memória se o qs já foi materializado; em uso como predicado inline pode ser N+1 — mitigação: usar `visible_posts_for` como qs, não `can_view_post` em loop

## Critério de revisão

Reavalie se `visible_posts_for` ultrapassar 60 linhas: extrair para `social/visibility.py`.



---

## 7. Onda 3c — Gestão Completa de Conta Privada e Pedidos de Seguir

Implementado na Onda 3c, consolidando as transições de visibilidade e o ciclo de vida dos pedidos de seguir:

### 7.1 Semântica das Transições de Privacidade (`PATCH /api/users/profile/`)

- **Autenticação & Segurança**: Exige `IsAuthenticated`, token CSRF válido e rate limiting (`UserRateThrottle`). Resposta mínima estrita: `{"username": "...", "is_private": bool}`.
- **Transição Privada → Pública**:
  - Todos os pedidos de seguir pendentes direcionados ao usuário (`Follow.objects.filter(followed=user, status=Follow.Status.PENDING)`) são convertidos para `status=Follow.Status.ACTIVE` em uma **única transação atômica** (`transaction.atomic`), de forma idempotente.
  - **Decisão Arquitetural (Sem notificações em massa)**: A aprovação em lote ao tornar a conta pública **não despacha notificações aos solicitantes**. *Justificativa*: Prevenir degradação de performance por enfileiramento em massa (fan-out spike) e evitar comportamento anti-spam/ruído na caixa de entrada dos usuários.
  - **Efeito nos Posts**: Posts com visibilidade `FOLLOWERS` tornam-se imediatamente acessíveis aos novos seguidores agora ativos; posts com visibilidade `CIRCLE` permanecem estritamente restritos aos membros com `is_close_friend=True`.
- **Transição Pública → Privada**:
  - Seguidores ativos existentes permanecem com `status=active`.
  - Novas tentativas de seguir passam a ser criadas como `status=pending`.
  - Posts públicos antigos do autor tornam-se **invisíveis para não-seguidores** em todas as superfícies (perfil, feed, explorar e busca global).

### 7.2 Ciclo de Vida dos Pedidos de Seguir

- **Listagem (`GET /api/social/follow-requests/`)**:
  - Restrito exclusivamente ao próprio dono da conta.
  - Paginação eficiente por cursor (keyset pagination por `id` DESC).
  - Serializer mínimo contendo estritamente `id`, `username`, `avatar`, `created_at`.
  - Exclui bilateralmente quaisquer usuários envolvidos em bloqueio (`Block.objects.filter(...)`).
- **Aceitação (`POST /api/social/follow-requests/<username>/accept/`)**:
  - Retorna `404 Not Found` se não existir pedido pendente (proteção contra IDOR e requisições repetidas).
  - Idempotente: uma segunda chamada consecutiva retorna 404 sem duplicar notificações.
  - Execução restrita ao próprio alvo do pedido.
  - Rate limiting ativo via throttle.
  - Dispara notificação para quem solicitou (`notify_follow_request_accepted`), respeitando as supressões do motor (bloqueio bilateral e silenciamento) via `transaction.on_commit`.
- **Recusa (`POST /api/social/follow-requests/<username>/reject/`)**:
  - Retorna `404 Not Found` se não existir pedido pendente (proteção IDOR).
  - Exclui o registro de `Follow` em silêncio (sem disparar nenhuma notificação ao solicitante).
  - Rate limiting ativo via throttle.
- **Bloqueio Bidirecional**:
  - Ao bloquear um usuário via `POST /api/social/block/<username>/`, quaisquer relacionamentos de `Follow` (sejam ativos ou pedidos pendentes) são removidos em ambas as direções.

### 7.3 Registro Histórico do Vazamento da Busca
- O vazamento na busca de posts (`search_posts` sem filtro de visibilidade ou checagem de bloqueio) existiu no repositório entre os commits `e98f432` e a implementação do módulo central de visibilidade na Onda 3a. O teste adversarial de busca roda no CI com banco PostgreSQL prevenindo qualquer regressão.
