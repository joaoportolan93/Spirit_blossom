# ADR-N11 — Logging e observabilidade

**Status:** Aceito  
**Data:** 2026-10-30  
**Decisores:** Comitê de 10 especialistas (ToT)

## Contexto

Infra solo, sem equipe de SRE. Logs precisam ser estruturados para debugging, mas sem complexidade de stack de observabilidade.

## Decisão

**structlog + tabela `AccessLog` no Postgres.** Logs estruturados JSON via structlog. `AccessLog` registra IP (HMAC-hashed), porta, timestamp, user_id para conformidade com Marco Civil. **Validar com jurista** antes de produção.

**Trade-off registrado:** structlog adiciona dependência e configuração vs. `logging` padrão do Python. O benefício é log estruturado em JSON sem formatação manual — relevante quando os logs forem consumidos por ferramentas de agregação (ex: Loki, CloudWatch). Para uso solo em MVP, o custo é baixo mas real.

Pontuação 70/70 reflete ausência de alternativa superior identificada, não ausência de trade-offs.

## Alternativas consideradas

| Alternativa | Total | Eliminado? |
|---|---|---|
| structlog + AccessLog PG | 70 | Não |
| logging padrão + sem AccessLog | 55 | Não |
| Stack completa (Prometheus + Grafana) | 38 | Não |

## Consequências

**Positivas:**
- Logs JSON prontos para agregação por ferramentas externas (Loki, CloudWatch, etc.).
- AccessLog para conformidade legal com Marco Civil.

**Negativas / trade-offs:**
- structlog é dependência extra vs. `logging` padrão.
- AccessLog exige adequação LGPD (validar com jurista antes de produção).

## Critério de revisão

Adicionar Prometheus/Grafana no M3+ se o produto for para produção real.
