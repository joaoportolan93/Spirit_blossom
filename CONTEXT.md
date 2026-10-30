# Rede social generalista

Fork do Lumem sem temas de sonhos/espiritualidade/neurociência.

## Repositório

```
apps/backend/    Django 5.2 + DRF + Celery
apps/frontend/   React 18 + Vite + PWA
services/feed/   Rust (Axum) — stub M0, lógica na Fase 1
infra/           Docker Compose, Nginx
docs/adr/        12 Architecture Decision Records
docs/api/        Contratos JSON Schema
```

## Estado atual

- **Marco:** M0 — fundações concluídas
- **Próximo:** M1a — esqueleto backend (aguardar "continuar")

## Regras de nomenclatura

- Nome do produto: configurável via `APP_NAME` (settings.py) e `VITE_APP_NAME` (frontend env)
- Identifiers em código: sempre em inglês, neutros de produto
- Nunca escrever o nome literal do produto em código, configs ou arquivos que não sejam `brand.js` ou settings

## Decisões arquiteturais

Ver `docs/adr/` — um arquivo por nó de decisão (N1–N12).

## Plano completo

Ver `docs/PLANO.md`.

## Riscos

Ver `docs/RISCOS.md`.
