# ADR-N15: Motor de Comentários em Árvore, Navegação por Foco e Moderação de Conversas

## Status
Aceito (Atualizado — Onda 4b)

## Contexto
O Spirit Blossom necessitava de um motor completo de comentários em árvore (respostas aninhadas), corrigindo as vulnerabilidades críticas herdadas do Lumem identificadas em auditoria de segurança (`security_audit.md`):
1. **Recursão infinita de profundidade:** No Lumem, não havia teto técnico ao criar comentários, permitindo ataques DoS via cadeias de centenas de níveis.
2. **Esgotamento de memória por `Prefetch` em cascata:** Consultas aninhadas em 5 níveis causavam estouro de memória no backend.
3. **Vazamento de dados em exclusão lógica (LGPD):** O Lumem mantinha o texto e o autor no banco de dados ao marcar `excluido=True`.
4. **Vulnerabilidades de autorização (IDOR) e moderação indevida:** O Lumem permitia que donos do post apagassem permanentemente comentários de terceiros sem rastreabilidade e sem preservar a árvore de respostas.
5. **Poluição visual e quebra de conector:** Conectores verticais de thread interrompidos por bordas horizontais no modo Focar e ícones não padronizados.

---

## Decisões

### 1. Separação Arquitetural e Modelo de Dados
- **App Dedicado:** App `comments` completamente desacoplado de `core`.
- **Identificadores UUIDv7:** O modelo `Comment` utiliza UUIDv7 sequencial no tempo como chave primária, indexado para inserções de alta escala.
- **Relacionamentos e Campos:**
  - `post`: chave estrangeira para `core.Post`.
  - `author`: chave estrangeira para `User` (`null=True`, `SET_NULL` para suportar anonimização LGPD).
  - `parent`: autorreferência (`Comment`, `null=True`, `CASCADE`).
  - `depth`: inteiro representando o nível na árvore (0 = comentário raiz).
  - `likes_count` e `replies_count`: contadores atômicos denormalizados.
  - `is_deleted`, `is_edited`, `edited_at`: flags de ciclo de vida e auditoria.
  - `is_hidden`, `hidden_at`, `hidden_by`, `hidden_reason`: campos para moderação de comentários ocultos.

### 2. Teto de Profundidade e Navegação por "Focar"
- **Limite Técnico Estrito:** `MAX_COMMENT_DEPTH = 50` em `comments/services.py`. Tentativas de comentar além do nível 50 retornam erro `400 Bad Request`.
- **Sem Achatamento Artificial:** A árvore mantém a estrutura hierárquica real intacta em qualquer nível.
- **Modo Focar (Twitter/X Style Focus):**
  - No feed/post: exibe comentários de profundidade 0 com prévias diretas até nível 2 com conectores em "L".
  - Nível 3+: clique no card navega para a rota de Foco (`?comment=<id>`).
  - O conector vertical entre o post original, os nós ancestrais e o comentário focado ("Hero") é contínuo, sem bordas horizontais divisórias cortando o traçado.
  - O endpoint `GET /api/comments/<id>/thread/` entrega em uma única consulta: resumo do post, ancestrais sanitizados, o nó "Hero" e as respostas paginadas.

### 3. Consultas em Lote O(1) sem N+1
- O seletor `list_post_comments_with_preview` executa exatamente **3 consultas SQL em lote**:
  1. Busca dos comentários de profundidade 0 (paginados por cursor).
  2. Busca em lote de todas as respostas de profundidade 1 cujos `parent_id` estejam no conjunto de nível 0.
  3. Busca em lote de todas as respostas de profundidade 2 cujos `parent_id` estejam no conjunto de nível 1.
- Montagem da árvore em memória em O(N), eliminando `Prefetch` aninhado e garantindo tempo de resposta constante.

### 4. Paginação por Cursor Composto Estável
- Suporte a três modos de ordenação via cursores base64 estáveis:
  - `recent`: `(created_at, id)`.
  - `likes`: `(likes_count, created_at, id)`.
  - `relevance`: score composto ponderado (engajamento + recência).

### 5. Moderação pelo Dono do Post: Ocultar Respostas (Twitter Style)
- **Proibição de Exclusão de Terceiros:** O dono da publicação **não pode** excluir comentários de outros usuários. Ele possui a prerrogativa exclusiva de **ocultar** comentários.
- **Endpoints de Ocultação:**
  - `POST /api/comments/<id>/hide/`: Oculta o comentário e toda a subárvore dele para todos os terceiros. Idempotente. Retorna `404 Not Found` se o requisitante não for o dono do post.
  - `DELETE /api/comments/<id>/hide/`: Reexibe o comentário oculto (apenas para o dono do post; demais recebem 404).
  - `GET /api/posts/<id>/hidden-comments/`: Retorna a lista paginada de comentários ocultos daquela publicação (apenas acessível pelo dono do post; terceiros recebem 404).
- **Regras de Visibilidade e Vazamento de Comentários Ocultos:**
  - **Dono do post:** Visualiza o comentário com indicador de oculto e opção de "Reexibir" na aba "Respostas ocultas" ou via modal.
  - **Autor do comentário:** Continua vendo o próprio comentário normalmente na árvore (sem selo de alerta ou notificação punitiva), para mitigar comportamento hostil ou tentativas de evasão.
  - **Terceiros e Anônimos:** O comentário oculto e todas as suas respostas são completamente excluídos da árvore pública.
  - **Como Ancestral no Focar:** Se um comentário oculto for ancestral de uma conversa pública acessada via link direto, ele é renderizado como placeholder sanitizado (`is_placeholder=True`, `content_text=""`, `author=None`).
  - **Contadores e Notificações:** Comentários ocultos são subtraídos do contador público `comments_count` do post e nenhum evento de notificação é disparado a partir de interações dentro de subárvores ocultas.

### 6. Ciclo de Vida de Exclusão (LGPD) e Poda Reversa
- **Autorização de Exclusão:** Restrita unicamente ao **autor do comentário**.
- **Nó com Descendentes (Tombstone):**
  - O nó é marcado como lápide (`is_deleted = True`).
  - O banco armazena string vazia `""` ou indicador estrito, e a API retorna `content_text=""` e `author=None`.
  - O frontend é responsável por renderizar a string traduzida (`[comentário excluído]`), sem avatar com ponto de interrogação `?`, sem `@` solto e sem indicador de `editado`.
- **Nó Folha (Sem Filhos):** Exclusão física permanente no banco de dados com **poda reversa** recursiva dos nós ancestrais que permaneceram como lápides órfãs.

### 7. Menu de Ações «…» Padronizado e Ícones Centralizados
- **No Card de Post:**
  - *Dono:* Editar (apenas texto, limite de 3000 caracteres, marca `editado`, sem alterar visibilidade), Excluir (transacional, limpando comentários, curtidas, salvos e notificações), Respostas ocultas (N) quando `hidden_comments_count > 0`.
  - *Outros:* Silenciar @usuário, Bloquear @usuário (com confirmação).
- **Nos Comentários:**
  - *Autor:* Editar e Excluir.
  - *Dono do Post (em comentário alheio):* Ocultar resposta / Reexibir.
  - *Outros:* Silenciar @usuário e Bloquear @usuário.
- **Ícones Centralizados:** Componente unificado `CommentIcons.jsx` fornecendo `HeartIcon` (coração), `SpeechBubbleIcon` (balão de fala) e `BookmarkIcon` (marcador).
- **Truncamento de Texto:** Cards no feed, Explorar e Busca truncam textos longos acima de 280 caracteres com botão "Mostrar mais" / "Mostrar menos". A página de detalhes do post (`PostPage`) exibe o texto integral.

### 8. Integridade de Contadores e Proteção AST
- Modificações em instâncias de `Post` respeitam o teste arquitetural estrito (`TestArchitecturePostObjectsDirect`): nenhuma mutação direta de `Post.objects` fora dos módulos autorizados. Todas as alterações passam por helpers de serviço (`increment_post_comments_count`, `decrement_post_comments_count`, etc.).

---

## Consequências
- Proteção robusta contra ataques de negação de serviço e vazamento de dados pessoais.
- Preservação da integridade da árvore com moderação civilizada e não destrutiva.
- Cobertura de testes automatizados superior a 95% no backend e mais de 90% no frontend.

