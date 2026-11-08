# ADR-N22 — Descoberta: Busca de Usuários e Feed Explorar

**Status:** Aceito  
**Data:** 2026-11-06  
**Decisores:** Orquestrador  
**Referência:** Estudo Lumem (`docs/lumem-study/01-privacidade-e-vazamentos.md`), Auditoria Fork (`docs/lumem-study/02-auditoria-do-fork.md`)

---

## Contexto

O Lumem possui vulnerabilidades no Explorar e Busca:
1. `SearchView` não exclui usuários bloqueados ou bloqueadores.
2. Explorar expõe posts sem checar bloqueio/silenciamento bilateral.
3. Não há rate limiting rígido em endpoints de busca.

No Spirit Blossom, busca e exploração devem falhar fechadas para privacidade.

---

## Decisão

### 1. Busca de Usuários (`GET /api/users/search/?q=...`)
- **Filtro estrito**: prefixo de `username` (`username__istartswith=query.lower()`).
- **Tamanho mínimo**: 2 caracteres. Se menor, retorna 400 (`Parâmetro 'q' deve ter no mínimo 2 caracteres`).
- **Exclusões obrigatórias**:
  - Contas inativas (`is_active=False` ou `status != "active"`).
  - Bloqueio bidirecional: exclui quem o viewer bloqueou e quem bloqueou o viewer.
  - O próprio viewer.
- **Campos expostos**: `id`, `username`, `avatar`, `is_private`.
- **Campos proibidos**: `email`, `birth_date`, `status`, `is_staff`, `google_sub`.
- **Throttle**: 30 requisições/minuto por usuário autenticado.

### 2. Feed Explorar (`GET /api/feed/explore/?cursor=...`)
- **Apenas posts públicos**: `visibility == Post.Visibility.PUBLIC`.
- **Exclusões obrigatórias**:
  - Posts de autores bloqueados pelo viewer ou que bloquearam o viewer.
  - Posts de autores que o viewer silenciou (`Mute`).
  - Posts do próprio viewer (Explorar é para descoberta externa).
- **Paginação**: Keyset pagination via UUIDv7 (`id < cursor` ordenado por `-id`).
- **Contrato JSON**: Compatível com `docs/api/feed-contract.json`:
  ```json
  {
    "items": [
      {
        "post_id": "018d...",
        "reason": "explore",
        "cursor": "018d..."
      }
    ],
    "next_cursor": "018d..."
  }
  ```

### 3. Busca de Posts (`GET /api/posts/search/?q=...`)
- **Correção da Falha 1 (Auditoria A2)**:
  - Todo resultado deve passar por `visible_posts_for(user)`.
  - Exclui autores bloqueados em ambos os sentidos.
  - Respeita visibilidade (`PUBLIC` sempre; `FOLLOWERS` só se seguidor ativo; `CIRCLE` só se amigo próximo ativo).

---

## Contratos JSON dos Endpoints

### `GET /api/users/search/?q={query}&limit=20`
```json
{
  "results": [
    {
      "id": "0192f1b0-...",
      "username": "alice",
      "avatar": "http://.../media/avatars/alice.png",
      "is_private": false
    }
  ]
}
```

### `GET /api/feed/explore/?cursor={uuid}`
```json
{
  "items": [
    {
      "post_id": "0192f1b5-...",
      "reason": "explore",
      "cursor": "0192f1b5-..."
    }
  ],
  "next_cursor": "0192f1b5-..."
}
```
