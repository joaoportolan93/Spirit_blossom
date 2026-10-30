# ADR-N7 — Linguagem do frontend

**Status:** Aceito  
**Data:** 2026-10-30  
**Decisores:** Comitê de 10 especialistas (ToT)

## Contexto

Fork do Lumem (~80% reaproveitável, mas exige renomeações mecânicas de campos). Desenvolvedor solo. TypeScript oferece segurança de tipos mas exige configuração extra.

A queda do N7-JS de v1 para v4 ocorreu em **Re** (Reversibilidade/Esforço), não em S. TypeScript incremental (allowJs) não é reescrita completa, mas ainda exige tsconfig, type stubs e ajustes de build — custo real para desenvolvedor solo.

## Decisão

**JavaScript ES2022+** (não TypeScript). Reutilização do Lumem com renomeação mecânica de campos da API no M1b. TypeScript incremental (allowJs) avaliado e descartado por Re=4 vs JS Re=5 — custo de configuração sem benefício imediato para base de código pequena.

## Alternativas consideradas

| Alternativa | Total | Eliminado? |
|---|---|---|
| JavaScript ES2022+ | 65 | Não |
| TypeScript incremental (allowJs) | 62 | Não |
| TypeScript completo | 48 | Não |

## Consequências

**Positivas:**
- Reaproveitamento direto do Lumem sem atrito de configuração.
- Sem configuração extra de build (tsconfig, type stubs, ajustes de bundler).

**Negativas / trade-offs:**
- Sem verificação estática de tipos; bugs de tipo só aparecem em runtime ou nos testes.

## Critério de revisão

Migrar para TypeScript incremental no M3+ se a base de código crescer acima de 50 componentes.
