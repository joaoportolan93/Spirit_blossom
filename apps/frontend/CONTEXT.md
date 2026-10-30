# Frontend React

PWA com React 18, Vite, Tailwind CSS, React Query e i18next.

## Convenções

- **Marca**: único ponto de definição em `src/config/brand.js` → `APP_NAME`.
  - Em componentes: `import { APP_NAME } from "@/config/brand"`.
  - Nunca escreva o nome literal do produto em componentes.
- **i18n**: chaves neutras em `src/locales/pt-BR.json` e `src/locales/en.json`.
- **API**: `src/services/api.js` — axios com `withCredentials: true` e interceptor de CSRF.
- **PWA**: `vite-plugin-pwa` (Workbox) — não use `sw.js` manual.
- **Identifiers de campo**: use os nomes retornados pela API (English). Renomear em M1b se a API mudar.

## Estrutura (criada em M1b)

```
src/
  config/       brand.js, constantes
  services/     api.js (axios), queryClient.js
  pages/        Login, Register, Timeline, Profile, Compose
  components/   UI reutilizável
  locales/      pt-BR.json, en.json
  i18n.js
```

## Passo de renomeação mecânica (M1b)

Ao sincronizar com a API final do M1a, rodar:

```bash
# Exemplo: campo mudou de "conteudo_texto" para "content_text"
grep -r "conteudo_texto" src/ --include="*.js" --include="*.jsx" -l | \
  xargs sed -i 's/conteudo_texto/content_text/g'
```

Repetir para cada campo renomeado conforme lista em `docs/PLANO.md`.
