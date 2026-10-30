# Registro de riscos

> Atualizado a cada marco. Riscos resolvidos são movidos para a seção "Encerrados".

## Riscos ativos

| ID | Categoria | Descrição | Probabilidade | Impacto | Mitigação |
|---|---|---|---|---|---|
| R1 | Técnico | `GeneratedField` com `SearchVectorField` pode não ser suportado pelo Django ORM | Média | Alto | Spike no início do M1a; Plan B (GinIndex funcional) pronto como fallback |
| R2 | Técnico | Build Rust cross-compile para `aarch64` em CI x86 requer toolchain adicional | Alta | Médio | CI compila para host nativo por enquanto; `NOT VERIFIED` em ARM64 |
| R3 | Segurança | CSRF em staging pode falhar se `CSRF_TRUSTED_ORIGINS` não incluir `https://` | Alta | Alto | Teste manual em staging descrito em `infra/CONTEXT.md`; coberto por `SECURE_PROXY_SSL_HEADER` |
| R4 | Segurança | Conta suspensa pode continuar renovando JWT enquanto o refresh não expirar | Média | Alto | `TokenRefreshView` valida `user.is_active` e `user.status` (M1a) |
| R5 | Segurança | Media protegida retorna 404 (não 403) para acesso direto — comportamento correto do `internal` do Nginx | Baixa | Baixo | Testes esperam 404; comportamento documentado aqui |
| R6 | Legal | Tabela `AccessLog` (IP hasheado) pode exigir adequação à LGPD e ao Marco Civil | Média | Alto | **Validar com jurista** antes do M1a entrar em produção; IP armazenado como HMAC |
| R7 | Produto | "~80% de reaproveitamento do Lumem" é otimista dado o volume de renomeações | Alta | Médio | Passo mecânico de renomeação documentado em `docs/PLANO.md` e `apps/frontend/CONTEXT.md` |
| R8 | Técnico | Tabelas `OutstandingToken` / `BlacklistedToken` crescem sem limpeza | Baixa | Médio | `flush_expired_tokens` no Celery beat (03:30 diário) |
| R9 | Infra | ARM64 Oracle Cloud: imagens Docker não verificadas localmente em x86 | Alta | Médio | Marcado `NOT VERIFIED`; verificar em ambiente ARM antes do deploy |

## Encerrados

| ID | Descrição | Resolução |
|---|---|---|
| — | — | — |

## Notas

- **Validar com jurista**: R6 (`AccessLog`) antes de qualquer deploy em produção.
- **NOT VERIFIED**: build ARM64 (R2, R9) — requer ambiente nativo para confirmar.
- Riscos de segurança com probabilidade Alta ou Impacto Alto são revisados a cada marco.

