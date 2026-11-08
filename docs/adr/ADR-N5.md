# ADR-N5 — Upload e servição de mídia

**Status:** Aceito  
**Data:** 2026-10-30  
**Decisores:** Comitê de 10 especialistas (ToT)

## Contexto

O produto armazena imagens de perfil e mídia anexada a posts. Mídia de posts privados deve ser servida exclusivamente para usuários autorizados — arquivos não podem ser acessíveis diretamente via URL pública. A infraestrutura alvo é um servidor Oracle ARM com Nginx e Django.

## Decisão

**Nginx X-Accel-Redirect + Celery para deleção física.**

### Fluxo de servição

1. Cliente faz request para `/api/media/<path>/`.
2. Django executa verificação de autorização (usuário autenticado + permissão de acesso ao post).
3. Se autorizado, Django responde `200` com header `X-Accel-Redirect: /protected-media/<path>` e body vazio.
4. Nginx intercepta o header e serve o arquivo diretamente do disco, sem passar pelo Python.
5. Clientes externos que acessem `/protected-media/<path>` diretamente recebem **404** (comportamento correto do `internal` do Nginx).

### Configuração Nginx obrigatória

```nginx
location /protected-media/ {
    internal;
    alias /var/media/;
}
```

### Deleção física de arquivos

Ao deletar um `Post` ou trocar imagem de perfil:
```python
# services.py
storage.delete(instance.image.name)  # deleta do disco antes
instance.delete()                    # deleta do banco
```

Tarefas de limpeza assíncronas (órfãos) delegadas ao Celery quando necessário.

> **Nota sobre testes:** testes que verificam acesso direto a `/protected-media/<path>` devem esperar **404**, não 403. O Nginx com `internal` recusa clientes externos com 404 por design — este é o comportamento correto a ser afirmado nos testes de integração.

## Alternativas consideradas

| Alternativa | Total | Eliminado? |
|---|---|---|
| Nginx X-Accel-Redirect + Celery | 65 | Não |
| CDN externo (S3 + CloudFront) | 52 | Não |
| Django serve diretamente | 48 | Não |

## Consequências

**Positivas:**
- Nginx eficiente para I/O de arquivos estáticos — Django não bloqueia workers.
- Autorização de acesso controlada por Django antes de qualquer byte de arquivo ser transferido.
- Sem dependência de CDN externo ou custo de egress em cloud storage.
- Deleção física evita acúmulo de arquivos órfãos no disco.

**Negativas / trade-offs:**
- Configuração `internal` no Nginx é obrigatória e crítica — um erro deixa arquivos públicos.
- Acesso direto retorna 404 (não 403), o que pode confundir debugging inicial.
- Sem CDN: latência de mídia dependente da localização geográfica do servidor Oracle ARM.
- Escala limitada à capacidade de disco da instância.

## Critério de revisão

Reavaliar migração para CDN externo (ex.: Cloudflare R2, AWS S3 + CloudFront) se: (a) o volume de mídia superar a capacidade de disco da instância Oracle ARM; (b) a latência de download de mídia tornar-se problema percebido por usuários fora da região do servidor.
