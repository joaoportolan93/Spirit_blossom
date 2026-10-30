# ADR-N1 — Estrutura do repositório

**Status:** Aceito  
**Data:** 2026-10-30  
**Decisores:** Comitê de 10 especialistas (ToT)

## Contexto

Desenvolvedor solo. O produto possui três camadas técnicas distintas: backend Django, frontend React e um serviço Rust dedicado ao feed. Cada camada exige toolchain, lockfile e CI independentes, mas scripts compartilhados e configurações de infra precisam coexistir sem duplicação.

## Decisão

**Monorepo Modular** — um único repositório Git com a seguinte estrutura de diretórios:

```
apps/
  backend/    # Django
  frontend/   # React
services/
  feed/       # Rust
infra/         # Terraform, Docker Compose, scripts compartilhados
docs/          # ADRs e documentação
```

CI configurado com `paths-filter` por camada: alterações em `apps/backend/**` disparam apenas o pipeline Django; alterações em `services/feed/**` disparam apenas o pipeline Rust, etc.

## Alternativas consideradas

| Alternativa | Total | Eliminado? |
|---|---|---|
| Monorepo Modular | 61 | Não |
| Flat (tudo na raiz) | 65 | Não |
| Multirepo | 52 | Não |

> **Nota sobre o vencedor:** A alternativa Flat obteve pontuação numericamente superior (65 vs 61), mas a diferença de 4 pontos é menor que a incerteza de estimativa dos especialistas. O Monorepo Modular foi escolhido pelo argumento qualitativo mais forte: isolamento de toolchain ARM64/Rust no CI e lockfile Cargo separado sem poluir a raiz do repositório.

## Consequências

**Positivas:**
- CI isolado por camada via `paths-filter` — pipelines independentes sem interferência.
- Dockerfile dedicado por app, com contexto de build mínimo.
- Toolchain Rust (`rustup`, `cargo`) confinado ao subdiretório `services/feed`.
- Scripts e configurações de infra centralizados em `infra/`, sem duplicação.

**Negativas / trade-offs:**
- Paths no CI precisam de prefixo explícito (ex.: `apps/backend/`, não apenas `backend/`).
- Cada subdiretório de app deve conter um `CONTEXT.md` descrevendo sua responsabilidade, para facilitar navegação por desenvolvedor solo sem memória contextual imediata.

## Critério de revisão

Reavaliar para Multirepo se o número de apps/serviços crescer acima de 5 e a navegação do monorepo tornar-se visivelmente custosa (ex.: `git log` ruidoso, CI base demorado mesmo com `paths-filter`).
