import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { PostCard } from "../components/PostCard";
import { api } from "../services/api";
import "../i18n";

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

function renderCard(post, props = {}) {
  return render(
    <MemoryRouter>
      <PostCard post={post} {...props} />
    </MemoryRouter>
  );
}

describe("PostCard Component — Curtidas, Salvos e Comentários", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const basePost = {
    id: "post-123",
    content_text: "Conteúdo para teste de interação",
    created_at: new Date().toISOString(),
    author: { username: "alice" },
    visibility: "public",
    is_liked: false,
    likes_count: 5,
    is_bookmarked: false,
    bookmarks_count: 2,
    comments_count: 4,
  };

  it("1. Renderiza conteúdo, autor e contadores iniciais", () => {
    renderCard(basePost);

    expect(screen.getByTestId("post-content")).toHaveTextContent("Conteúdo para teste de interação");
    expect(screen.getByText("@alice")).toBeInTheDocument();
    expect(screen.getByTestId("likes-count")).toHaveTextContent("5");
    expect(screen.getByTestId("bookmarks-count")).toHaveTextContent("2");
    expect(screen.getByTestId("comments-count")).toHaveTextContent("4");
    expect(screen.queryByTestId("post-circle-badge")).not.toBeInTheDocument();
  });

  it("2. Exibe badge de círculo quando visibilidade for circle", () => {
    const circlePost = { ...basePost, visibility: "circle" };
    renderCard(circlePost);

    expect(screen.getByTestId("post-circle-badge")).toBeInTheDocument();
  });

  it("3. Alterna curtida com update otimista e chama endpoints corretos", async () => {
    vi.spyOn(api, "post").mockResolvedValueOnce({});
    vi.spyOn(api, "delete").mockResolvedValueOnce({});

    renderCard(basePost);

    const likeBtn = screen.getByTestId("like-button");
    const likesCount = screen.getByTestId("likes-count");

    // Curtir (POST)
    fireEvent.click(likeBtn);
    expect(likesCount).toHaveTextContent("6");
    expect(likeBtn).toHaveClass("text-rose-500");

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith("/api/posts/post-123/like/");
    });

    // Descurtir (DELETE)
    fireEvent.click(likeBtn);
    expect(likesCount).toHaveTextContent("5");
    expect(likeBtn).not.toHaveClass("text-rose-500");

    await waitFor(() => {
      expect(api.delete).toHaveBeenCalledWith("/api/posts/post-123/like/");
    });
  });

  it("4. Reverte estado de curtida se chamada da API falhar", async () => {
    vi.spyOn(api, "post").mockRejectedValueOnce(new Error("Erro de rede"));

    renderCard(basePost);

    const likeBtn = screen.getByTestId("like-button");
    const likesCount = screen.getByTestId("likes-count");

    fireEvent.click(likeBtn);
    expect(likesCount).toHaveTextContent("6");

    await waitFor(() => {
      expect(likesCount).toHaveTextContent("5");
      expect(likeBtn).not.toHaveClass("text-rose-500");
    });
  });

  it("5. Alterna salvamento (bookmark) com update otimista e trata erro", async () => {
    vi.spyOn(api, "post").mockResolvedValueOnce({});
    vi.spyOn(api, "delete").mockResolvedValueOnce({});

    renderCard(basePost);

    const bookmarkBtn = screen.getByTestId("bookmark-button");
    const bookmarksCount = screen.getByTestId("bookmarks-count");

    // Salvar
    fireEvent.click(bookmarkBtn);
    expect(bookmarksCount).toHaveTextContent("3");
    expect(bookmarkBtn).toHaveClass("text-pink-400");

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith("/api/posts/post-123/bookmark/");
    });

    // Remover dos salvos
    fireEvent.click(bookmarkBtn);
    expect(bookmarksCount).toHaveTextContent("2");
    expect(bookmarkBtn).not.toHaveClass("text-violet-400");

    await waitFor(() => {
      expect(api.delete).toHaveBeenCalledWith("/api/posts/post-123/bookmark/");
    });

    // Erro reverte
    vi.spyOn(api, "post").mockRejectedValueOnce(new Error("Falha"));
    fireEvent.click(bookmarkBtn);
    await waitFor(() => {
      expect(bookmarksCount).toHaveTextContent("2");
    });
  });

  it("6. Clicar no botão de comentários navega para a página do post", () => {
    renderCard(basePost);

    const commentBtn = screen.getByTestId("comment-button");
    fireEvent.click(commentBtn);

    expect(mockNavigate).toHaveBeenCalledWith("/posts/post-123");
  });

  it("7. Clicar no card do post navega para a página do post", () => {
    renderCard(basePost);

    const card = screen.getByTestId("post-card");
    fireEvent.click(card);

    expect(mockNavigate).toHaveBeenCalledWith("/posts/post-123");
  });

  it("8. Em modo detalhe (isDetail=true), clicar no card não dispara navegação", () => {
    renderCard(basePost, { isDetail: true });

    const card = screen.getByTestId("post-card");
    fireEvent.click(card);

    expect(mockNavigate).not.toHaveBeenCalled();

    // Clicar no botão de comentário em modo detalhe foca input se existir
    const input = document.createElement("input");
    input.setAttribute("data-testid", "root-comment-input");
    const focusSpy = vi.spyOn(input, "focus");
    document.body.appendChild(input);

    const commentBtn = screen.getByTestId("comment-button");
    fireEvent.click(commentBtn);
    expect(focusSpy).toHaveBeenCalled();
    document.body.removeChild(input);
  });

  it("9. Trunca texto longo (> 280 chars) e alterna com Mostrar mais / menos", () => {
    const longText = "A".repeat(350);
    const longPost = { ...basePost, content_text: longText };
    renderCard(longPost);

    expect(screen.getByTestId("show-more-btn")).toHaveTextContent("Mostrar mais");
    expect(screen.getByTestId("post-content")).toHaveTextContent("A".repeat(280) + "...");

    fireEvent.click(screen.getByTestId("show-more-btn"));
    expect(screen.getByTestId("show-more-btn")).toHaveTextContent("Mostrar menos");
    expect(screen.getByTestId("post-content")).toHaveTextContent(longText);

    fireEvent.click(screen.getByTestId("show-more-btn"));
    expect(screen.getByTestId("show-more-btn")).toHaveTextContent("Mostrar mais");
  });

  it("10. Dono do post abre menu «…» e edita texto com sucesso", async () => {
    vi.spyOn(api, "patch").mockResolvedValueOnce({
      data: {
        ...basePost,
        content_text: "Texto editado com sucesso",
        is_edited: true,
      },
    });

    renderCard(basePost, { currentUser: { username: "alice" } });

    // Abre menu
    const menuBtn = screen.getByTestId("post-menu-btn");
    fireEvent.click(menuBtn);

    const editBtn = screen.getByTestId("post-edit-btn");
    fireEvent.click(editBtn);

    const textarea = screen.getByTestId("post-edit-textarea");
    expect(textarea).toHaveValue("Conteúdo para teste de interação");

    fireEvent.change(textarea, { target: { value: "Texto editado com sucesso" } });
    const saveBtn = screen.getByTestId("save-post-edit-btn");
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(api.patch).toHaveBeenCalledWith("/api/posts/post-123/", {
        content_text: "Texto editado com sucesso",
      });
      expect(screen.getByTestId("post-content")).toHaveTextContent("Texto editado com sucesso");
    });
  });

  it("11. Dono do post abre menu «…» e cancela edição", () => {
    renderCard(basePost, { currentUser: { username: "alice" } });

    fireEvent.click(screen.getByTestId("post-menu-btn"));
    fireEvent.click(screen.getByTestId("post-edit-btn"));

    const cancelBtn = screen.getByTestId("cancel-post-edit-btn");
    fireEvent.click(cancelBtn);

    expect(screen.queryByTestId("post-edit-textarea")).not.toBeInTheDocument();
    expect(screen.getByTestId("post-content")).toHaveTextContent("Conteúdo para teste de interação");
  });

  it("12. Dono do post abre menu «…» e exclui o post com confirmação", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.spyOn(api, "delete").mockResolvedValueOnce({});
    const mockOnDelete = vi.fn();

    renderCard(basePost, { currentUser: { username: "alice" }, onDelete: mockOnDelete });

    fireEvent.click(screen.getByTestId("post-menu-btn"));
    const deleteBtn = screen.getByTestId("post-delete-btn");
    fireEvent.click(deleteBtn);

    await waitFor(() => {
      expect(api.delete).toHaveBeenCalledWith("/api/posts/post-123/");
      expect(mockOnDelete).toHaveBeenCalledWith("post-123");
    });
  });

  it("13. Dono do post visualiza botão de Respostas Ocultas quando houver comentários ocultos", () => {
    const hiddenPost = { ...basePost, hidden_comments_count: 3 };
    const mockViewHidden = vi.fn();

    const { rerender } = renderCard(hiddenPost, { currentUser: { username: "alice" }, onViewHidden: mockViewHidden });

    fireEvent.click(screen.getByTestId("post-menu-btn"));
    const hiddenBtn = screen.getByTestId("post-hidden-replies-btn");
    expect(hiddenBtn).toHaveTextContent("Respostas ocultas (3)");

    fireEvent.click(hiddenBtn);
    expect(mockViewHidden).toHaveBeenCalledWith("post-123");

    // Sem onViewHidden navega para ?tab=hidden
    rerender(
      <MemoryRouter>
        <PostCard post={hiddenPost} currentUser={{ username: "alice" }} />
      </MemoryRouter>
    );
    fireEvent.click(screen.getByTestId("post-menu-btn"));
    fireEvent.click(screen.getByTestId("post-hidden-replies-btn"));
    expect(mockNavigate).toHaveBeenCalledWith("/posts/post-123?tab=hidden");
  });

  it("14. Terceiro abre menu «…» e silencia ou bloqueia autor com confirmação", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.spyOn(api, "post").mockResolvedValue({});

    renderCard(basePost, { currentUser: { username: "bob" } });

    // Backdrop fecha menu
    fireEvent.click(screen.getByTestId("post-menu-btn"));
    const backdrop = document.querySelector(".fixed.inset-0");
    if (backdrop) {
      fireEvent.click(backdrop);
    }

    // Silenciar
    fireEvent.click(screen.getByTestId("post-menu-btn"));
    const muteBtn = screen.getByTestId("post-mute-btn");
    fireEvent.click(muteBtn);

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith("/api/social/mute/alice/");
    });

    // Bloquear
    fireEvent.click(screen.getByTestId("post-menu-btn"));
    const blockBtn = screen.getByTestId("post-block-btn");
    fireEvent.click(blockBtn);

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith("/api/social/block/alice/");
    });
  });

  it("15. Bloquear autor em modo detalhe (isDetail=true) redireciona para home '/'", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.spyOn(api, "post").mockResolvedValue({});

    renderCard(basePost, { currentUser: { username: "bob" }, isDetail: true });

    fireEvent.click(screen.getByTestId("post-menu-btn"));
    const blockBtn = screen.getByTestId("post-block-btn");
    fireEvent.click(blockBtn);

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith("/");
    });
  });

  it("16. Cancela diálogos de bloqueio e silenciamento no post sem disparar chamadas", () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    const postSpy = vi.spyOn(api, "post");

    renderCard(basePost, { currentUser: { username: "bob" } });

    fireEvent.click(screen.getByTestId("post-menu-btn"));
    fireEvent.click(screen.getByTestId("post-mute-btn"));

    fireEvent.click(screen.getByTestId("post-menu-btn"));
    fireEvent.click(screen.getByTestId("post-block-btn"));

    expect(postSpy).not.toHaveBeenCalled();
  });
});

