# ADR-N10 — Estratégia de testes

**Status:** Aceito  
**Data:** 2026-10-30  
**Decisores:** Comitê de 10 especialistas (ToT)

## Contexto

Desenvolvedor solo. Testes devem proteger sem custo de manutenção excessivo.

## Decisão

**Pirâmide lean** — maioria unitária/integração, E2E em job separado no CI (só em push para main). Mínimo de 58 testes no M1a. E2E com Playwright cobrindo o fluxo crítico (cadastro→post→seguir→ver).

## Alternativas consideradas

| Alternativa | Total | Eliminado? |
|---|---|---|
| Pirâmide lean + E2E separado | 65 | Não |
| 100% cobertura | 42 | Não |
| Só linters + testes de API | 32 | **Sim — Se=3 (eliminatório)** |

## Consequências

**Positivas:**
- CI rápido — E2E não bloqueia PRs normais.
- Testes de segurança obrigatórios (CSRF, visibilidade, bloqueio bidirecional).

**Negativas / trade-offs:**
- E2E pode ficar desatualizado se rodado raramente.
- Playwright requer browser instalado no CI.

## Critério de revisão

Aumentar cobertura E2E no M2+ conforme fluxos críticos crescem.
