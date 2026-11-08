# ADR-N9 — Embeddings e busca semântica

**Status:** Aceito  
**Data:** 2026-10-30  
**Decisores:** Comitê de 10 especialistas (ToT)

## Contexto

Busca semântica e recomendação personalizada requerem embeddings. Infraestrutura Oracle ARM sem GPU.

## Decisão

**Deferred para M4.** No M4: MiniLM-L12-v2 via `sentence-transformers`, CPU-only, singleton com `@lru_cache(maxsize=1)`. Truncamento em **126 tokens úteis** (128 − [CLS] − [SEP], conforme `model.max_seq_length=128`).

**Mudança de comportamento registrada:** a regra de truncamento em 126 tokens aplica-se ao conteúdo como um todo. Hashtags no final do post **não** têm espaço reservado — em posts com 126 tokens ou mais de texto, hashtags são truncadas. Comportamento anterior (Lumem) reservava espaço para hashtags. Isso é uma mudança intencional: simplicidade > preservação de hashtags em posts longos.

## Alternativas consideradas

| Alternativa | Total | Eliminado? |
|---|---|---|
| Deferred M4 (MiniLM CPU) | 70 | Não |
| Sem embeddings | 55 | Não |
| OpenAI Embeddings API | 38 | Não (Re=1, NP=2) |

## Consequências

**Positivas:**
- Zero custo no M1.
- Sem GPU necessária; MiniLM funciona em ARM64.

**Negativas / trade-offs:**
- Recomendação personalizada ausente até M4.
- Hashtags truncadas em posts longos (mudança de comportamento vs. Lumem).

## Critério de revisão

Implementar no M4 junto com algoritmo Rev3.
