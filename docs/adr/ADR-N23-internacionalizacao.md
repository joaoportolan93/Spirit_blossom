# ADR-N23: Estratégia de Internacionalização (i18n) e Localização (l10n)

## Status
Aceito

## Contexto
O Spirit Blossom atende usuários de múltiplos idiomas (inicialmente Português do Brasil `pt-BR` e Inglês `en`), exigindo comunicação fluida tanto na interface do usuário (web) quanto nos retornos de erro da API REST e mensagens assíncronas geradas em segundo plano (como e-mails transacionais via Celery).

Havia divergência de formatos entre ecossistemas (JSON vs `.po` gettext) e dependência de ferramentas do sistema operacional (binários `gettext.exe` no Windows).

## Decisão

### 1. Backend (Django REST Framework)
- **Mecanismo:** Padrão GNU gettext com arquivos portáveis `.po` e binários compilados `.mo`.
- **Configurações:**
  - `USE_I18N = True`
  - `LANGUAGES = [("pt-br", "Português"), ("en", "English")]`
  - `LOCALE_PATHS = [BASE_DIR / "locale"]`
  - `LocaleMiddleware` posicionado estritamente entre `SessionMiddleware` e `CommonMiddleware` para resolver o idioma a partir do cabeçalho HTTP `Accept-Language`.
- **Convenção de Código:** Strings marcadas com `gettext_lazy` (`_()`) no escopo de modelos/serializers e `gettext` em views/services. O `msgid` de referência é mantido em inglês, com traduções em `locale/pt_BR/LC_MESSAGES/django.po` e `locale/en/LC_MESSAGES/django.po`.
- **Processamento Assíncrono (Celery / E-mails):**
  - E-mails transacionais (como recuperação de senha) e tarefas em segundo plano utilizam `with translation.override(user_lang):` para garantir que o destinatário receba a mensagem no seu idioma de preferência, independentemente do locale padrão do servidor ou worker.
- **Ferramenta de Compilação (Windows / CI):**
  - Adoção da biblioteca pure-Python `polib` (`polib>=1.2.0`), dispensando qualquer instalação de binários de sistema (`gettext.exe` ou pacotes externos).
  - Um script auxiliar compila `.po` para `.mo` diretamente em memória ou disco sem requerer ferramentas externas.
- **Versionamento dos Arquivos `.mo`:**
  - Decisão: os arquivos binários `.mo` compilados são versionados no repositório Git para garantir que os ambientes de CI/CD, contêineres Docker e instâncias sem ferramentas de build executem imediatamente as traduções em tempo de carregamento do Django sem custos adicionais de build.

### 2. Frontend (React / Vite)
- **Mecanismo:** Mantido `react-i18next` com catálogos em formato JSON nativo (`src/locales/pt-BR.json` e `src/locales/en.json`). Não há migração do frontend para `.po`, preservando simplicidade, carregamento assíncrono e tipagem leve.
- **Propagação para a API:**
  - O interceptor de requisições do Axios (`services/api.js`) anexa dinamicamente o cabeçalho `Accept-Language` com o código do idioma ativo retornado por `i18n.language`.
- **Garantia de Qualidade:**
  - Teste automatizado no Vitest (`src/test/i18n.test.js`) valida recursivamente a paridade estrita de 100% das chaves entre `pt-BR.json` e `en.json`, falhando preventivamente no CI se qualquer chave for adicionada em um idioma e esquecida no outro.

## Consequências
- Paridade semântica entre front e back.
- Sem dependências de binários de compilação em desenvolvimento local no Windows.
- O e-mail e tarefas assíncronas respeitam a língua do destinatário.

