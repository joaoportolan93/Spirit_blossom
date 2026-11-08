# ADR-N8 — Notificações push

**Status:** Aceito  
**Data:** 2026-10-30  
**Decisores:** Comitê de 10 especialistas (ToT)

## Contexto

Notificações em tempo real. FCM (Google Firebase) cria dependência de SDK + conta Firebase. WebSockets têm custo de infraestrutura alto para desenvolvedor solo.

## Decisão

**Polling no M1a; VAPID nativo no M2+.**

- **M1a:** polling React Query a cada 30s.
- **M2+:** Web Push VAPID sem SDK Firebase. Model `PushDevice` com campos `endpoint` (URL do push service), `p256dh` (chave pública do cliente), `auth_key` (segredo HMAC).

**Nota sobre lock-in:** VAPID elimina o SDK Firebase e a conta Firebase, mas o Chrome ainda entrega push via infraestrutura Google e Safari via Apple. O claim "sem lock-in Google" é impreciso — correto é "sem SDK/conta Firebase".

### Campos do model `PushDevice`

```
endpoint: URLField       # URL do push service do browser
p256dh: TextField        # chave pública ECDH do cliente (base64url)
auth_key: TextField      # segredo de autenticação (base64url)
user: FK(User)
created_at: DateTimeField
```

## Alternativas consideradas

| Alternativa | Total | Eliminado? |
|---|---|---|
| Polling M1 + VAPID M2+ | 68 | Não |
| FCM (Firebase) | 52 | Não (Re=2, NP=2; Se=4 — não eliminado por segurança) |
| WebSockets | 40 | **Sim — Se=3 (eliminatório)** |

## Consequências

**Positivas:**
- Sem SDK Firebase; sem conta Firebase.
- VAPID é padrão W3C.

**Negativas / trade-offs:**
- Push ainda transita por infraestrutura dos browsers (Google/Apple).
- Implementação VAPID exige biblioteca server-side (`py-vapid` ou equivalente).

## Critério de revisão

Implementar VAPID no M2. Reavaliar SSE se polling mostrar custo excessivo.
