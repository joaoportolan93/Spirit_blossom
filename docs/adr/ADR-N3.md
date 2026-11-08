# ADR-N3 — Autenticação

**Status:** Aceito  
**Data:** 2026-10-30  
**Decisores:** Comitê de 10 especialistas (ToT)

## Contexto

Rede social com React SPA como cliente principal e possibilidade futura de clientes mobile nativos. O projeto é um fork do Lumem, que já utiliza `SimpleJWT`. Segurança CSRF é requisito inegociável para qualquer esquema baseado em cookies.

## Decisão

**JWT em cookie httpOnly** com os seguintes detalhes de implementação:

- Dois cookies httpOnly: `access_token` (curta duração) e `refresh_token` (longa duração).
- Classe `CookieJWTAuthentication` customizada, com `_CSRFCheck` espelhando o padrão do `SessionAuthentication` do DRF.
- `/api/auth/refresh/` e `/api/auth/logout/` com `authentication_classes=[]` e `_enforce_csrf()` explícito na view (evita loop de autenticação + mantém proteção CSRF).
- Endpoint `/api/csrf/` para o frontend obter o cookie CSRF antes do primeiro request.
- Configuração SimpleJWT: `ROTATE_REFRESH_TOKENS=True`, `BLACKLIST_AFTER_ROTATION=True`.

### Histórico de variações de pontuação (para registro)

| Versão | JWT Cookie S | JWT Cookie Re | Sessão S | Sessão Re |
|---|---|---|---|---|
| v1 | 4 | 3 | 4 | 4 |
| v2 | 4 | 4 | 4 | 4 |
| v3 | 3 | 4 | 4 | 3 |
| v4 (final) | 5 | 4 | 4 | 3 |

**Pontuação final consolidada:** JWT Cookie httpOnly **68** vs Sessão Django **64**.

Motivo legítimo para JWT sobre Sessão: Lumem já tem SimpleJWT (S=5, reaproveitamento real de código existente); Re=4 vs Re=3 da Sessão — qualquer cliente não-browser futuro exigiria adicionar JWT _sobre_ sessão, custo maior que manter JWT desde o início.

> **Trade-off honesto:** JWT exige classe de autenticação customizada, 2 views customizadas, endpoint `/csrf/`, interceptor Axios no frontend e aproximadamente 12 testes de segurança. Sessão Django não exigiria nenhum desses componentes extras. A escolha é defensável pelo reaproveitamento do Lumem e pela extensibilidade futura, mas não é trivialmente superior à Sessão.

## Alternativas consideradas

| Alternativa | Total | Eliminado? |
|---|---|---|
| JWT Cookie httpOnly | 68 | Não |
| Sessão Django | 64 | Não |
| Bearer Token (Authorization header) | 42 | **Sim — Se=2 (eliminatório)** |

> Bearer Token eliminado por exposição ao JavaScript (XSS) sem mitigação nativa equivalente ao httpOnly.

## Consequências

**Positivas:**
- Reaproveitamento direto do SimpleJWT já presente no Lumem.
- Tokens não acessíveis por JavaScript (httpOnly) — mitigação de XSS.
- Independência futura de clientes não-browser sem custo adicional de arquitetura.
- Rotação automática de refresh token reduz janela de exploração.

**Negativas / trade-offs:**
- Código de segurança próprio (`CookieJWTAuthentication`) — risco de bug se não testado rigorosamente.
- Testes obrigatórios com `enforce_csrf_checks=True` para validar CSRF real.
- Interceptor de Axios obrigatório no frontend para envio automático do header `X-CSRFToken`.
- Endpoint `/csrf/` adicional na API.

## Critério de revisão

Reavaliar migração para Sessão Django se: (a) bugs de CSRF forem encontrados em produção; (b) o custo de manutenção da classe `CookieJWTAuthentication` superar o benefício percebido; (c) nenhum cliente não-browser for implementado até o M3.
