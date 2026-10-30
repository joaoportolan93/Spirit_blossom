# ADR-N12 — Serviço de feed Rust

**Status:** Aceito  
**Data:** 2026-10-30  
**Decisores:** Comitê de 10 especialistas (ToT)

## Contexto

Feed personalizado (Rev3) pode se beneficiar de Rust (performance, segurança de memória). No M0, apenas stub.

## Decisão

**types.rs + /health somente no M0.** Structs `FeedItem`, `FeedReason`, `FeedResponse` em `src/types.rs` definem o contrato compartilhado. `/health` endpoint. Lógica real no M4 (Fase 1).

Contrato neutro em `docs/api/feed-contract.json` (JSON Schema Draft-07). Backend Python valida respostas contra o schema com `jsonschema` + `FormatChecker`. O schema (não o Rust) é a fonte de verdade do contrato — o Python não é obrigado a chamar o Rust para respeitar o contrato.

Pontuação: S=4 (não 5) — overhead de CI Rust sem funcionalidade real no M0 é um custo real.

## Alternativas consideradas

| Alternativa | Total | Eliminado? |
|---|---|---|
| types.rs + /health | 67 | Não |
| Stub HTTP Python | 58 | Não |
| Sem stub | 50 | Não |

## Consequências

**Positivas:**
- Tipos Rust e schema JSON estabelecem contrato cedo, antes da implementação real.
- CI Rust validado desde M0.

**Negativas / trade-offs:**
- S=4 (custo de CI sem benefício funcional imediato no M0).
- Build ARM64 não verificado em x86.

## Critério de revisão

Implementar lógica real no M4. Se Rust mostrar fricção excessiva para dev solo, reavaliar migração para Python puro.
