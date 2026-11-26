# Backend Django

Aplicativo principal: Django 5.2 + DRF + SimpleJWT + Celery.

## Estrutura do Backend (estilo Lumem)

O backend é organizado em um único app de domínio (`core`), estruturado por pastas de responsabilidade:

```
apps/backend/
├── config/             Configurações Django, URLs raiz, Celery
├── core/               App principal (novas ondas com domínio próprio devem virar apps Django dedicados, como `comments/`)
│   ├── models/         Submódulos por domínio (users, posts, social, notifications, feature_flags, moderation)
│   ├── admin.py        Administração Django consolidada
│   ├── authentication.py Cookie JWT + CSRF
│   ├── throttles.py    Limitadores de taxa
│   ├── tasks.py        Tarefas assíncronas Celery
│   ├── factories.py    Fábricas para testes (FactoryBoy)
│   ├── urls.py         URLs centralizadas sob /api/*
│   ├── migrations/     0001_initial.py+
│   ├── views/          Subpacotes/módulos por assunto (auth, posts, reports, feed, notifications, admin/, social/)
│   ├── serializers/    Divididos por assunto (auth, posts, social, feed, notifications)
│   ├── services/       Lógica de escrita e seletores divididos por assunto
│   ├── utils/          Utilitários de visibilidade central (visibility.py)
│   └── tests_*.py      Testes por assunto (auth, csrf, feed, interactions, posts, search, social, visibility, etc.)
```

## Convenções

- **Modelos**: English, snake_case. `User`, `UserProfile`, `Post`, `PostLike`, `PostBookmark`, `Draft`, `Follow`, `Block`, `Mute`, `Notification`, `AccessLog`.
- **UUID7** via biblioteca `uuid6` (`pk = models.UUIDField(default=uuid6.uuid7, primary_key=True)`).
- **Serviço / Seletor**: lógica de negócio em `core/services/` e `core/utils/visibility.py`, nunca em models ou views.
- **FTS**: sempre `websearch_to_tsquery` com config `'simple'` (bilíngue pt-BR / EN).
- **CSRF**: veja `core/authentication.py` para o fluxo completo.

## Variáveis de ambiente obrigatórias

Ver `../../.env.example` e `config/settings.py`.

## Rodar localmente (sem Docker)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../../.env.example .env  # preencha os valores
python manage.py migrate
python manage.py runserver
```
