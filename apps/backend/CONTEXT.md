# Backend Django

Aplicativo principal: Django 5.2 + DRF + SimpleJWT + Celery.

## Estrutura de apps (criados em M1a)

```
config/         Configurações, URLs raiz, Celery
accounts/       Usuários, autenticação, autorização
posts/          Publicações, busca FTS
social/         Follow, Block, Mute
feed/           Seletor de feed "Seguindo" (chrono M1a, Rev3 M4)
notifications/  Notificações (polling M1, VAPID M2+)
```

## Convenções

- **Modelos**: English, snake_case. `User`, `Post`, `Follow`, `Block`, `Mute`, `Notification`, `AccessLog`.
- **UUID7** via biblioteca `uuid6` (campo `pk = models.UUIDField(default=uuid6.uuid7, primary_key=True)`).
- **Serviço / Seletor**: lógica de negócio em `selectors.py` e `services.py`, nunca em models ou views.
- **FTS**: sempre `websearch_to_tsquery` com config `'simple'` (bilíngue pt-BR / EN).
- **CSRF**: veja `accounts/authentication.py` para o fluxo completo.

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
