# ADR-N4 — Algoritmo de feed

**Status:** Aceito  
**Data:** 2026-10-30  
**Decisores:** Comitê de 10 especialistas (ToT)

## Contexto

O feed "Seguindo" (cronológico por pessoas que o usuário segue) é requisito obrigatório para o M1a. O feed "Para Você" (personalizado por relevância) exige embeddings vetoriais e infraestrutura de ML — complexidade fora do escopo inicial e do milestone de entrega do M1a.

## Decisão

**SQL cronológico no M1a; algoritmo personalizado Rev3 no M4.**

Detalhes de implementação do M1a:

- **Paginação:** keyset cursor com `id__lt=cursor_uuid ORDER BY id DESC` — evita `OFFSET` crescente, estável com inserções concorrentes.
- **Índice:** `(author_id, id DESC)` declarado em `Meta.indexes` do model `Post`.
- **Query base:**
  ```python
  # selectors.py
  def get_following_feed(*, user, cursor=None, limit=20):
      following_ids = user.following.values_list("id", flat=True)
      qs = Post.objects.filter(author_id__in=following_ids)
      if cursor:
          qs = qs.filter(id__lt=cursor)
      return qs.order_by("-id").select_related("author")[:limit]
  ```

Rev3 (M4): a ser especificado em ADR separado quando pgvector e embeddings (N9) forem implementados.

## Alternativas consideradas

| Alternativa | Total | Eliminado? |
|---|---|---|
| SQL cronológico M1 + Rev3 M4 | 68 | Não |
| Só cronológico permanentemente | 55 | Não |
| Rev3 imediato (desde M1) | 45 | Não |

## Consequências

**Positivas:**
- Entrega rápida do feed no M1a sem dependência de GPU ou infraestrutura de ML.
- SQL puro — sem serviço externo, sem latência de rede adicional.
- Keyset cursor garante performance constante independente do volume de posts.
- Decisão reversível: SQL cronológico pode ser substituído por Rev3 sem quebrar a API (mesma interface de cursor).

**Negativas / trade-offs:**
- Refatoração necessária no M4 quando Rev3 entrar — custo técnico planejado e esperado.
- Ausência de feed "Para Você" pode reduzir retenção inicial de usuários menos engajados em redes sociais.
- Índice `(author_id, id DESC)` precisará ser revisado para Rev3 (possivelmente índice adicional).

## Critério de revisão

Implementar Rev3 quando embeddings (ADR-N9) entrarem em produção no M4. Reavaliar algoritmo cronológico puro apenas se métricas de retenção do M1a mostrarem problema grave atribuível à ausência de personalização.
