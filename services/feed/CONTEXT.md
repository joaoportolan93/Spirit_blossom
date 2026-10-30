# Feed Service (Rust)

Serviço Axum responsável pelo algoritmo de feed personalizado.

**Estado atual:** stub M0 — apenas `/health`. Nenhuma lógica de ranking.

## Roadmap

| Marco | Funcionalidade |
|---|---|
| M0 | Stub `/health` |
| Fase 1 | Recebe `user_id`, consulta Postgres, retorna IDs rankeados |
| Fase 2+ | Algoritmo Rev3, embeddings (delegado pelo backend Python) |

## Tipos estáveis (contrato)

Definidos em `src/types.rs` e espelhados em `docs/api/feed-contract.json`.
O backend Python valida as respostas contra o JSON Schema.

## Build local

```bash
cargo build
cargo test
cargo clippy
```

## Variáveis de ambiente

| Variável | Padrão | Descrição |
|---|---|---|
| `FEED_PORT` | `3000` | Porta de escuta |
| `RUST_LOG` | `info` | Nível de log |

