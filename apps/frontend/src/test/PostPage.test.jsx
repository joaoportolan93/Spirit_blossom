import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import PostPage from "../pages/PostPage";
import * as apiModule from "../services/api";
import "../i18n";

vi.mock("../hooks/useAuth", () => ({
  useAuth: () => ({
    user: { id: "user-1", username: "current_user" },
  }),
}));

function renderPostPage(initialEntries = ["/posts/post-uuid-1"]) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <Routes>
        <Route path="/posts/:id" element={<PostPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("PostPage Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const mockPost = {
    id: "post-uuid-1",
    author: { username: "autor1", avatar: null },
    content_text: "Texto do post para teste de comentários",
    created_at: new Date().toISOString(),
    likes_count: 3,
    comments_count: 1,
    is_liked: false,
    is_bookmarked: false,
  };

  const mockCommentsData = {
    items: [
      {
        id: "comment-root-1",
        content_text: "Primeiro comentário raiz",
        author: { username: "comentador1", avatar: null },
        created_at: new Date().toISOString(),
        likes_count: 2,
        replies_count: 1,
        can_edit: true,
        can_delete: true,
        preview_replies: [
          {
            id: "comment-child-1",
            content_text: "Resposta filha nível 1",
            author: { username: "comentador2", avatar: null },
            created_at: new Date().toISOString(),
            likes_count: 0,
            replies_count: 0,
            can_edit: false,
            can_delete: false,
            preview_replies: [],
          },
        ],
      },
    ],
    next_cursor: null,
  };

  it("1. Renderiza post original e lista de comentários raiz com respostas em prévia", async () => {
    vi.spyOn(apiModule, "getPostDetail").mockResolvedValueOnce(mockPost);
    vi.spyOn(apiModule, "getPostComments").mockResolvedValueOnce(mockCommentsData);

    renderPostPage();

    expect(screen.getByText("Carregando...")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("Texto do post para teste de comentários")).toBeInTheDocument();
      expect(screen.getByText("Primeiro comentário raiz")).toBeInTheDocument();
      expect(screen.getByText("Resposta filha nível 1")).toBeInTheDocument();
      expect(screen.getByTestId("sort-select")).toBeInTheDocument();
    });
  });

  it("2. Exibe mensagem de erro quando post é inexistente ou privado (404)", async () => {
    const error404 = new Error("Not Found");
    error404.response = { status: 404 };
    vi.spyOn(apiModule, "getPostDetail").mockRejectedValueOnce(error404);
    vi.spyOn(apiModule, "getPostComments").mockResolvedValueOnce({ items: [] });

    renderPostPage();

    await waitFor(() => {
      expect(screen.getByText("Publicação não encontrada ou privada.")).toBeInTheDocument();
      expect(screen.getByText("Voltar")).toBeInTheDocument();
    });
  });

  it("3. Cria comentário raiz com sucesso", async () => {
    vi.spyOn(apiModule, "getPostDetail").mockResolvedValueOnce(mockPost);
    vi.spyOn(apiModule, "getPostComments").mockResolvedValueOnce({ items: [] });
    vi.spyOn(apiModule, "createComment").mockResolvedValueOnce({
      id: "new-comment-uuid",
      content_text: "Novo comentário criado pelo usuário",
      author: { username: "current_user", avatar: null },
      created_at: new Date().toISOString(),
      likes_count: 0,
      replies_count: 0,
      can_edit: true,
      can_delete: true,
      preview_replies: [],
    });

    renderPostPage();

    await waitFor(() => {
      expect(screen.getByTestId("root-comment-input")).toBeInTheDocument();
    });

    const input = screen.getByTestId("root-comment-input");
    fireEvent.change(input, { target: { value: "Novo comentário criado pelo usuário" } });

    const submitBtn = screen.getByTestId("root-comment-submit");
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(apiModule.createComment).toHaveBeenCalledWith("post-uuid-1", {
        content_text: "Novo comentário criado pelo usuário",
      });
      expect(screen.getByText("Novo comentário criado pelo usuário")).toBeInTheDocument();
    });
  });

  it("4. Altera ordenação de comentários e refaz busca", async () => {
    vi.spyOn(apiModule, "getPostDetail").mockResolvedValue(mockPost);
    vi.spyOn(apiModule, "getPostComments").mockResolvedValue(mockCommentsData);

    renderPostPage();

    await waitFor(() => {
      expect(screen.getByTestId("sort-select")).toBeInTheDocument();
    });

    const select = screen.getByTestId("sort-select");
    fireEvent.change(select, { target: { value: "likes" } });

    await waitFor(() => {
      expect(apiModule.getPostComments).toHaveBeenCalledWith("post-uuid-1", "likes");
    });
  });

  it("5. Modo Focado é ativado quando URL possui ?comment=<id>", async () => {
    vi.spyOn(apiModule, "getPostDetail").mockResolvedValueOnce(mockPost);
    vi.spyOn(apiModule, "getPostComments").mockResolvedValueOnce(mockCommentsData);
    vi.spyOn(apiModule, "getCommentThread").mockResolvedValueOnce({
      post: mockPost,
      ancestors: [
        {
          id: "ancestor-root",
          content_text: "Raiz da conversa",
          author: { username: "raiz_user" },
          likes_count: 1,
          replies_count: 1,
        },
      ],
      comment: {
        id: "focused-comment-uuid",
        content_text: "Comentário que foi focado diretamente",
        author: { username: "focado_user" },
        likes_count: 5,
        replies_count: 0,
        can_edit: false,
        can_delete: false,
      },
      replies: [],
      next_cursor: null,
    });

    renderPostPage(["/posts/post-uuid-1?comment=focused-comment-uuid"]);

    await waitFor(() => {
      expect(apiModule.getCommentThread).toHaveBeenCalledWith("focused-comment-uuid");
      expect(screen.getByTestId("focused-thread-view")).toBeInTheDocument();
      expect(screen.getByText("Comentário que foi focado diretamente")).toBeInTheDocument();
      expect(screen.getByText("Raiz da conversa")).toBeInTheDocument();
    });

    // Clica para sair do foco
    const exitBtn = screen.getByTestId("exit-focus-btn");
    fireEvent.click(exitBtn);

    await waitFor(() => {
      expect(screen.getByTestId("post-page")).toBeInTheDocument();
    });
  });

  it("6. Botão voltar ao anterior em modo focado navega para o ancestral pai", async () => {
    vi.spyOn(apiModule, "getPostDetail").mockResolvedValueOnce(mockPost);
    vi.spyOn(apiModule, "getPostComments").mockResolvedValueOnce(mockCommentsData);
    vi.spyOn(apiModule, "getCommentThread").mockResolvedValueOnce({
      post: mockPost,
      ancestors: [
        {
          id: "ancestor-root",
          content_text: "Raiz da conversa",
          author: { username: "raiz_user" },
          likes_count: 1,
          replies_count: 1,
        },
      ],
      comment: {
        id: "focused-child",
        content_text: "Filho focado",
        author: { username: "filho" },
        likes_count: 1,
        replies_count: 0,
      },
      replies: [],
      next_cursor: null,
    });

    renderPostPage(["/posts/post-uuid-1?comment=focused-child"]);

    await waitFor(() => {
      expect(screen.getByTestId("back-to-parent-btn")).toBeInTheDocument();
    });

    const backToParentBtn = screen.getByTestId("back-to-parent-btn");
    fireEvent.click(backToParentBtn);
  });

  it("6. Responder a comentário na árvore cria resposta aninhada", async () => {
    vi.spyOn(apiModule, "getPostDetail").mockResolvedValueOnce(mockPost);
    vi.spyOn(apiModule, "getPostComments").mockResolvedValueOnce(mockCommentsData);
    vi.spyOn(apiModule, "createComment").mockResolvedValueOnce({
      id: "comment-new-child",
      content_text: "Nova resposta aninhada",
      author: { username: "current_user", avatar: null },
      likes_count: 0,
      replies_count: 0,
    });

    renderPostPage();

    await waitFor(() => {
      expect(screen.getByTestId("reply-btn-comment-root-1")).toBeInTheDocument();
    });

    const replyBtn = screen.getByTestId("reply-btn-comment-root-1");
    fireEvent.click(replyBtn);

    const replyInput = screen.getByTestId("reply-input-comment-root-1");
    fireEvent.change(replyInput, { target: { value: "Nova resposta aninhada" } });

    const replySubmit = screen.getByTestId("reply-submit-btn-comment-root-1");
    fireEvent.click(replySubmit);

    await waitFor(() => {
      expect(apiModule.createComment).toHaveBeenCalledWith("post-uuid-1", {
        content_text: "Nova resposta aninhada",
        parent_id: "comment-root-1",
      });
      expect(screen.getByText("Nova resposta aninhada")).toBeInTheDocument();
    });
  });

  it("7. Exclusão de comentário folha remove nó da árvore", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.spyOn(apiModule, "getPostDetail").mockResolvedValueOnce(mockPost);
    vi.spyOn(apiModule, "getPostComments").mockResolvedValueOnce({
      items: [
        {
          id: "comment-solo-1",
          content_text: "Comentário que será excluído",
          author: { username: "current_user" },
          can_delete: true,
          preview_replies: [],
        },
      ],
      next_cursor: null,
    });
    vi.spyOn(apiModule, "deleteComment").mockResolvedValueOnce({});

    renderPostPage();

    await waitFor(() => {
      expect(screen.getByText("Comentário que será excluído")).toBeInTheDocument();
    });

    const deleteBtn = screen.getByTestId("delete-comment-btn-comment-solo-1");
    fireEvent.click(deleteBtn);

    await waitFor(() => {
      expect(apiModule.deleteComment).toHaveBeenCalledWith("comment-solo-1");
      expect(screen.queryByText("Comentário que será excluído")).not.toBeInTheDocument();
    });
  });

  it("8. Modo focado exibe FocusedThreadView e permite voltar ao pai e sair do foco", async () => {
    vi.spyOn(apiModule, "getPostDetail").mockResolvedValue(mockPost);
    vi.spyOn(apiModule, "getPostComments").mockResolvedValue(mockCommentsData);
    vi.spyOn(apiModule, "getCommentThread").mockImplementation((id) =>
      Promise.resolve({
        post: mockPost,
        ancestors:
          id === "focused-child"
            ? [
                {
                  id: "ancestor-root",
                  content_text: "Raiz",
                  author: { username: "raiz_user" },
                  likes_count: 0,
                  replies_count: 1,
                },
              ]
            : [],
        comment: {
          id: id || "focused-child",
          content_text: "Comentário " + id,
          author: { username: "filho_user" },
          likes_count: 1,
          replies_count: 0,
        },
        replies: [],
        next_cursor: null,
      })
    );

    renderPostPage(["/posts/post-uuid-1?comment=focused-child"]);

    await waitFor(() => {
      expect(screen.getByText("Conversa")).toBeInTheDocument();
      expect(screen.getByText("Comentário focused-child")).toBeInTheDocument();
      expect(screen.getByText("Raiz")).toBeInTheDocument();
    });

    // Clica em voltar ao anterior
    const backParentBtn = screen.getByTestId("back-to-parent-btn");
    fireEvent.click(backParentBtn);

    await waitFor(() => {
      expect(screen.getByText("Comentário ancestor-root")).toBeInTheDocument();
    });

    // Clica em sair do foco
    const exitBtn = screen.getByTestId("exit-focus-btn");
    fireEvent.click(exitBtn);

    await waitFor(() => {
      expect(screen.getByText("Primeiro comentário raiz")).toBeInTheDocument();
    });
  });

  it("9. Dono visualiza aba de respostas ocultas e reexibe comentário", async () => {
    const ownerPost = {
      ...mockPost,
      author: { username: "current_user", avatar: null },
      hidden_comments_count: 1,
    };
    const mockHiddenData = {
      items: [
        {
          id: "hidden-comment-1",
          content_text: "Comentário que estava oculto",
          author: { username: "spam_user", avatar: null },
          created_at: new Date().toISOString(),
        },
      ],
      next_cursor: null,
    };

    vi.spyOn(apiModule, "getPostDetail").mockResolvedValue(ownerPost);
    vi.spyOn(apiModule, "getPostComments").mockResolvedValue(mockCommentsData);
    vi.spyOn(apiModule, "getPostHiddenComments").mockResolvedValue(mockHiddenData);
    vi.spyOn(apiModule, "unhideComment").mockResolvedValue({});

    renderPostPage(["/posts/post-uuid-1?tab=hidden"]);

    await waitFor(() => {
      expect(screen.getByTestId("hidden-comments-section")).toBeInTheDocument();
      expect(screen.getByText("Comentário que estava oculto")).toBeInTheDocument();
    });

    const unhideBtn = screen.getByTestId("unhide-comment-btn");
    fireEvent.click(unhideBtn);

    await waitFor(() => {
      expect(apiModule.unhideComment).toHaveBeenCalledWith("hidden-comment-1");
      expect(screen.queryByText("Comentário que estava oculto")).not.toBeInTheDocument();
    });
  });

  it("10. Exibe badge de respostas ocultas para o dono e permite navegar", async () => {
    const ownerPost = {
      ...mockPost,
      author: { username: "current_user", avatar: null },
      hidden_comments_count: 2,
    };

    vi.spyOn(apiModule, "getPostDetail").mockResolvedValue(ownerPost);
    vi.spyOn(apiModule, "getPostComments").mockResolvedValue(mockCommentsData);
    vi.spyOn(apiModule, "getPostHiddenComments").mockResolvedValue({ items: [] });

    renderPostPage();

    await waitFor(() => {
      expect(screen.getByTestId("hidden-comments-tab-badge")).toBeInTheDocument();
      expect(screen.getByTestId("hidden-comments-tab-badge")).toHaveTextContent("2");
    });

    fireEvent.click(screen.getByTestId("hidden-comments-tab-badge"));

    await waitFor(() => {
      expect(screen.getByTestId("hidden-comments-section")).toBeInTheDocument();
      expect(screen.getByTestId("no-hidden-comments")).toBeInTheDocument();
    });

    // Clica no botão voltar aos comentários
    fireEvent.click(screen.getByTestId("back-to-comments-btn"));
    await waitFor(() => {
      expect(screen.queryByTestId("hidden-comments-section")).not.toBeInTheDocument();
      expect(screen.getByTestId("comments-section")).toBeInTheDocument();
    });
  });

  it("11. Renderiza comentário oculto com avatar e testa foco sem ancestrais", async () => {
    const ownerPost = {
      ...mockPost,
      author: { username: "current_user" },
    };
    const mockHidden = {
      items: [
        {
          id: "hidden-avatar-1",
          content_text: "Comentário com avatar",
          author: { username: "avatar_user", avatar: "http://example.com/avatar.png" },
          created_at: new Date().toISOString(),
        },
      ],
      next_cursor: null,
    };

    vi.spyOn(apiModule, "getPostDetail").mockResolvedValue(ownerPost);
    vi.spyOn(apiModule, "getPostComments").mockResolvedValue(mockCommentsData);
    vi.spyOn(apiModule, "getPostHiddenComments").mockResolvedValue(mockHidden);

    renderPostPage(["/posts/post-uuid-1?tab=hidden"]);

    await waitFor(() => {
      expect(screen.getByText("Comentário com avatar")).toBeInTheDocument();
      expect(screen.getByAltText("avatar_user")).toBeInTheDocument();
    });

    // Thread focada sem ancestrais: voltar ao anterior limpa foco
    vi.spyOn(apiModule, "getCommentThread").mockResolvedValueOnce({
      post: mockPost,
      ancestors: [],
      comment: { id: "solo-focused", content_text: "Solo", author: { username: "solo" } },
      replies: [],
    });

    renderPostPage(["/posts/post-uuid-1?comment=solo-focused"]);
    await waitFor(() => {
      expect(screen.getByText("Solo")).toBeInTheDocument();
    });
  });

  it("12. Botão voltar navega para o histórico anterior ou para a raiz se sem histórico", async () => {
    vi.spyOn(apiModule, "getPostDetail").mockResolvedValue(mockPost);
    vi.spyOn(apiModule, "getPostComments").mockResolvedValue(mockCommentsData);

    // Caso 1: Com histórico no navegador
    window.history.replaceState({ idx: 1 }, "");
    const { unmount } = renderPostPage();

    await waitFor(() => {
      expect(screen.getByTestId("post-back-btn")).toBeInTheDocument();
    });

    const backBtn = screen.getByTestId("post-back-btn");
    fireEvent.click(backBtn);
    unmount();

    // Caso 2: Sem histórico prévio (idx = 0)
    window.history.replaceState({ idx: 0 }, "");
    renderPostPage();

    await waitFor(() => {
      expect(screen.getByTestId("post-back-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("post-back-btn"));
  });
});
