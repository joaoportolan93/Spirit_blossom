# ADR-N24: Sistema Completo de Bloqueio e Silenciamento

## Status
Proposto (Aguardando Aprovação do Usuário para Execução da Onda 4c)

## Contexto
O Spirit Blossom necessita de um sistema abrangente e robusto de moderação pessoal composto por **Bloqueio** e **Silenciamento** de contas. Diferente de implementações ingênuas que deixam rastros ou dependem de limpezas em lote, o sistema deve garantir segurança máxima ao usuário que bloqueia, prevenção contra retaliação e conformidade com as diretrizes de privacidade e LGPD.

---

## Princípios Fundamentais

1. **Simetria Estrita (Nenhum dos dois vê o outro):**
   - O bloqueio é bidirecional em efeito de visibilidade: o usuário bloqueador não vê nada do bloqueado, e o usuário bloqueado não vê nada do bloqueador.
2. **Aplicação na Leitura (Read-time Enforcement):**
   - O bloqueio é avaliado dinamicamente no momento da consulta/leitura pelo banco de dados (`filter_blocked_content` / filtros de queryset).
   - A garantia de isolamento **nunca** depende de scripts de limpeza, background workers ou tarefas assíncronas.
3. **Reversibilidade Integral:**
   - Desbloquear remove a barreira de visibilidade imediatamente.
   - O desbloqueio **não restaura** seguidores nem inclusões em círculo de amigos (ações destrutivas ocorridas no momento do bloqueio são permanentes).
4. **Indistinguibilidade de "Não Encontrado" (404 Unforgeable):**
   - Tentativas de consultar perfil, post, comentário ou interagir com um usuário bloqueado (em qualquer direção) retornam HTTP `404 Not Found`.
   - O corpo (JSON), os headers e o tempo de resposta são indistinguíveis dos retornados para um recurso ou identificador realmente inexistente, prevenindo enumeração por oráculo de erro.

---

## Decisões Arquiteturais

### 1. Mecânica de Bloqueio (`POST/DELETE /api/social/block/<username>/`)
- **Idempotência:** Requisições repetidas para bloquear ou desbloquear a mesma conta retornam sucesso (200/204) sem duplicar registros nem levantar erro de chave única.
- **Auto-bloqueio Proibido:** Bloquear o próprio usuário (`user == target`) retorna `400 Bad Request`.
- **Transação Atômica (`transaction.atomic`):**
  Ao bloquear uma conta, uma transação única e atômica executa:
  1. Criação do registro de bloqueio (`Block(blocker=user, blocked=target)`).
  2. Remoção bilateral de seguimentos (`Follow.objects.filter(Q(follower=user, followed=target) | Q(follower=target, followed=user)).delete()`).
  3. Remoção bilateral de solicitações pendentes de seguir (`FollowRequest`).
  4. Remoção bilateral de marcações de círculo de amigos (`CloseFriend`).
  5. Ocultação retroativa de comentários antigos: os comentários já existentes do usuário bloqueado nos posts de quem bloqueou são marcados como ocultos (`is_hidden=True`, `hidden_reason='block'`).
  6. **Preservação de Dados Históricos:** Não remove curtidas passadas, itens favoritados nem histórico de notificações (esses dados permanecem íntegros no banco, mas são ativamente suprimidos e invisíveis na leitura).
- **Indexação Bidirecional:**
  - O modelo `Block` possui `unique_together = (("blocker", "blocked"),)` e índices compostos nos dois sentidos: `(blocker, blocked)` e `(blocked, blocker)`.

### 2. Mecânica de Silenciamento (`POST/DELETE /api/social/mute/<username>/`)
- **Assimétrico e Não Destrutivo:**
  - Silenciar afeta apenas a percepção do usuário que silenciou.
  - A relação de seguidor (`Follow`) permanece intacta nos dois sentidos.
  - O usuário silenciado **não é avisado**, nem notificado, nem recebe indicação visual.
- **Efeitos no Conteúdo:**
  - Oculta as publicações do silenciado no feed Seguindo e na aba Explorar.
  - Suprime todas as notificações futuras geradas por ações do usuário silenciado.
  - Em threads de comentários públicas, os comentários do usuário silenciado aparecem colapsados com a opção explícita «Mostrar comentário».

### 3. Matriz de Superfícies Afetadas

| Superfície | Comportamento sob Bloqueio | Comportamento sob Silenciamento |
| :--- | :--- | :--- |
| **Perfil** (`/api/users/<username>/`) | 404 indistinguível (nos dois sentidos) | Perfil normal, badge de silenciado para quem silenciou |
| **Posts** (`/api/posts/<id>/`) | 404 indistinguível | Post visível apenas por link direto |
| **Feed Seguindo** | Excluído nos dois sentidos | Excluído do feed |
| **Feed Explorar** | Excluído nos dois sentidos | Excluído do Explorar |
| **Busca (Pessoas e Posts)** | Usuário e posts excluídos nos dois sentidos | Visíveis normalmente |
| **Comentários na Conversa** | Nó substituído por placeholder colapsado «comentário de conta bloqueada» (respostas abaixo mantidas) | Comentário colapsado com botão «Mostrar» |
| **Modo Focar (Ancestral)** | Nó ancestral substituído por placeholder neutro sem metadados | Nó ancestral exibido normalmente |
| **Ações Ativas (Curtir/Salvar/Seguir/Comentar)** | Retorna 404 Not Found indistinguível | Permitido normalmente |
| **Favoritos / Bookmarks** | Ocultados na leitura | Visíveis normalmente |
| **Notificações** | Suprimidas retroativamente e ativamente na leitura | Suprimidas novas notificações do silenciado |
| **Contadores Denormalizados** | Contadores denormalizados mantidos atômicos no backend; renderização limpa no frontend | Contadores inalterados |
| **Listas Futuras (Seguidores, Sugestões, Menções)** | Excluídos bilateralmente | Mantidos |

> [!IMPORTANT]
> **Regra Obrigatória para Superfícies Futuras:**
> Qualquer nova funcionalidade, endpoint ou consulta que retorne listas de usuários, posts, mídias ou interações DEVE obrigatoriamente integrar a guarda centralizada de exclusão de bloqueio (`filter_blocked_users` / `filter_blocked_posts`). É vedada qualquer consulta direta a modelos sociais sem passar pela verificação de bloqueio.

### 4. Indistinguibilidade de 404 Not Found
- O endpoint de detalhes de perfil e de post deve retornar o mesmo payload JSON exato (`{"detail": "Não encontrado."}`), o mesmo `Content-Type: application/json` e os mesmos headers HTTP tanto para um identificador aleatório não existente quanto para um usuário/post bloqueado.
- Teste de paridade garantirá que tempo de resposta e headers não criem canal lateral (timing attack).

### 5. Interface com o Usuário (UI/UX)
- **Menu «…» Unificado:**
  - Cards de post, itens de comentário e página de perfil de outro usuário apresentam as opções «Bloquear @usuario» e «Silenciar @usuario» / «Desilenciar @usuario».
- **Confirmação e Desfazer:**
  - Ação de bloqueio requer diálogo claro de confirmação.
  - Após confirmação, exibe aviso (toast) com opção «Desfazer».
- **Configurações:**
  - Novas abas nas Configurações:
    - **Contas bloqueadas:** Lista de contas bloqueadas pelo usuário com botão «Desbloquear».
    - **Contas silenciadas:** Lista de contas silenciadas pelo usuário com botão «Reativar» (desilenciar).

### 6. Throttle e Limite de Taxa
- Os endpoints de bloquear e desbloquear serão protegidos por escopo dedicado de Rate Limiting (`10/minute` por IP/usuário) para evitar ataques de negação de serviço e abuso de alternância rápida de estado.

### 7. Exportação LGPD
- O relatório de exportação de dados do titular (`/api/users/export-data/`) deve incluir a lista de identificadores das contas que o usuário bloqueou (`blocked_by_me`).
- Em nenhuma hipótese o relatório informará quem bloqueou o usuário solicitante (`blocked_me`), preservando a segurança e a integridade de terceiros.

### 8. Estratégia de Testes e Mutação
- **Matriz de Superfícies:** Testes cobrindo cada uma das superfícies nos sentidos A bloqueia B e B bloqueia A.
- **Concorrência e Idempotência:** Testes de corrida entre seguir e bloquear, e bloqueio múltiplo idempotente.
- **Desbloqueio Limpo:** Verificação de que desbloquear não restaura relacionamentos de follow anteriores.
- **Teste de Indistinguibilidade:** Assert comparando resposta para ID inexistente vs ID bloqueado.
- **Teste de Mutação:** Teste automatizado que rompe deliberadamente o filtro de bloqueio e atesta que múltiplos testes de superfície falham imediatamente.
- **Teste de Arquitetura:** AST check impedindo consultas que acessem `Post` ou `Comment` sem invocar os seletores com suporte a bloqueio.

---

## Consequências
- Garantia de segurança e privacidade simétrica em conformidade com as melhores práticas anti-abuso.
- Reversibilidade segura sem acúmulo de dados zumbis.
- Isolamento total auditado por testes de mutação e cobertura mínima de 95% no backend e 84% no frontend.

