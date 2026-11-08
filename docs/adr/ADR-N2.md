# ADR-N2 — Padrão de organização do código Django

**Status:** Aceito  
**Data:** 2026-10-30  
**Decisores:** Comitê de 10 especialistas (ToT)

## Contexto

O backend Django abrange múltiplos domínios de negócio: `accounts`, `posts`, `social`, `feed` e `notifications`. Sem uma convenção explícita, há risco crescente de _fat models_ — models que acumulam lógica de negócio, dificultando testes unitários, reutilização e manutenção por desenvolvedor solo em contexto de longo prazo.

## Decisão

**Services + Selectors** — cada app Django terá dois módulos de lógica explícita:

- `selectors.py`: funções puras de consulta (somente leitura). Recebem parâmetros, retornam QuerySets ou valores. Sem efeitos colaterais.
- `services.py`: funções de mutação (criação, atualização, deleção, side-effects). Chamam seletores quando necessário.

Views e serializers permanecem finos: views delegam para services/selectors; serializers apenas serializam/desserializam dados.

```
accounts/
  models.py
  selectors.py   # get_user_by_id(), list_followers(), ...
  services.py    # create_user(), follow_user(), ...
  views.py       # fino — chama service/selector
  serializers.py # fino — só (de)serializa
```

## Alternativas consideradas

| Alternativa | Total | Eliminado? |
|---|---|---|
| Services + Selectors | 65 | Não |
| ViewSets genéricos | 57 | Não |
| Fat Models | 48 | **Sim — Se=3 (eliminatório)** |

## Consequências

**Positivas:**
- Lógica de negócio testável sem instanciar HTTP (sem `RequestFactory` obrigatório).
- Queries encapsuladas em seletores reutilizáveis entre views, tasks Celery e management commands.
- Models limpos — apenas campos, `Meta`, `__str__` e `clean()`.
- Erros de domínio centralizados nos services, não espalhados nas views.

**Negativas / trade-offs:**
- Mais arquivos por app — overhead inicial de criação.
- Exige disciplina contínua para não vazar lógica nas views (checklist de PR recomendado).
- Seletores complexos podem crescer e precisar de subdivisão.

## Critério de revisão

Se um único `selectors.py` ultrapassar 100 linhas ou conter lógica de domínios distintos, considerar dividir em `selectors/posts.py`, `selectors/feed.py`, etc. Reavaliar Fat Models apenas se o overhead de arquivos demonstrar custo real mensurável.

## Adendo (2026-11-07) — Consolidação no estilo Lumem (App único `core`)

Para eliminar duplicidade de pastas e espelhamento desnecessário, os 5 apps legados (`accounts`, `posts`, `social`, `feed`, `notifications`) foram consolidados no app único `core`.
A convenção de Services + Selectors permanece intacta sob `core/services/` (operações de escrita e leitura por domínio) e `core/utils/visibility.py` (seletor central de visibilidade). As views e serializers ficam organizados em `core/views/` e `core/serializers/`. Os testes passam a ser organizados por assunto em `core/tests_<assunto>.py`.

