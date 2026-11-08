# ADR-N6 — Busca full-text

**Status:** Aceito  
**Data:** 2026-10-30  
**Decisores:** Comitê de 10 especialistas (ToT)

## Contexto

O produto precisa de busca em conteúdo de posts. Os usuários digitam texto livre; o conteúdo é bilíngue (pt-BR e EN misturados no mesmo corpus). Stemming de configurações específicas de idioma (ex.: `'portuguese'` ou `'english'`) falha em texto bilíngue — palavras em inglês num post em português não seriam stemizadas corretamente e vice-versa.

## Decisão

**tsvector STORED + índice GIN com configuração `'simple'`.**

### Regras de implementação

- **Configuração:** sempre `'simple'` — sem stemming, tokenização por espaço/pontuação. Seguro para corpus bilíngue.
- **Query:** sempre `websearch_to_tsquery('simple', texto_usuario)` — aceita texto livre do usuário sem quebrar.  
  ⚠️ **Nunca usar `to_tsquery` diretamente com input do usuário** — quebra com termos compostos, parênteses ou caracteres especiais.
- **Anotação no seletor:** `sv` (não `search_vector`) para evitar conflito com o campo do model no Plano A.

### Implementação adotada — Plano A (`GeneratedField` — confirmado no spike do M1a)

O spike realizado pelo especialista E3 (Dados Postgres) confirmou que o Django 5.x
**exclui automaticamente** campos `GeneratedField` do INSERT/UPDATE via `SQLInsertCompiler`
(propriedade `field.generated = True`). O Postgres 16 aceita a expressão porque
`to_tsvector('simple'::regconfig, ...)` é estritamente `IMMUTABLE`.

```python
# posts/models.py — campo definitivo
search_vector = GeneratedField(
    expression=SearchVector("content_text", config="simple"),
    output_field=SearchVectorField(),
    db_persist=True,
)

class Meta:
    indexes = [
        models.Index(fields=["author", "-id"], name="posts_post_author_id_idx"),
        GinIndex(fields=["search_vector"], name="posts_post_search_gin"),
    ]
```

```python
# posts/selectors.py — query direta no campo STORED
def search_posts(*, query: str):
    sq = SearchQuery(query, config="simple", search_type="websearch")
    return Post.objects.filter(search_vector=sq)
```

> Plano B descartado. Não há necessidade de `annotate(sv=...)` no seletor com o campo STORED.

## Alternativas consideradas

| Alternativa | Total | Eliminado? |
|---|---|---|
| tsvector STORED + GIN | 68 | Não |
| Elasticsearch / OpenSearch | 44 | Não |
| `icontains` (LIKE) | 38 | Não |

## Consequências

**Positivas:**
- Full-text search nativo no PostgreSQL — sem dependência de serviço externo.
- Índice GIN garante performance em corpus grande sem varredura sequencial.
- Configuração `'simple'` funciona corretamente em corpus bilíngue pt-BR + EN.
- `websearch_to_tsquery` aceita input do usuário sem sanitização manual adicional.

**Negativas / trade-offs:**
- Configuração `'simple'` sem stemming: `"correr"` não encontra `"correndo"` — variações morfológicas não são cobertas.
- Busca apenas léxica (não semântica) — sem similaridade por significado.
- Busca semântica (pgvector) planejada apenas para M4 — retenção por descoberta de conteúdo limitada até lá.

## Critério de revisão

Adicionar busca semântica com `pgvector` no M4 (ver ADR-N9). Reavaliar stemming se análise de queries de usuários mostrar padrão predominante de um único idioma no corpus.
