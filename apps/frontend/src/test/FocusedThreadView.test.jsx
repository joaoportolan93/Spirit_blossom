import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import FocusedThreadView from "../components/FocusedThreadView";
import * as apiModule from "../services/api";
import "../i18n";

function renderThread(props) {
  return render(
    <MemoryRouter>
      <FocusedThreadView {...props} />
    </MemoryRouter>
  );
}

describe("FocusedThreadView Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
  });

  const mockPost = {
    id: "post-1",
    author: { username: "autor_original" },
    content_text: "Post principal",
  };

  const mockAncestors = [
    {
      id: "ancestor-1",
      content_text: "Comentário raiz ancestral",
      author: { username: "avo" },
      likes_count: 1,
      replies_count: 1,
    },
    {
      id: "ancestor-2",
      content_text: "Comentário pai intermediário",
      author: { username: "pai" },
      likes_count: 2,
      replies_count: 1,
    },
  ];

  const mockFocusedComment = {
    id: "focused-1",
    content_text: "Comentário focado em destaque HERO",
    author: { username: "focado_user" },
    likes_count: 10,
    replies_count: 2,
    can_edit: true,
    can_delete: true,
  };

  const mockReplies = [
    {
      id: "reply-1",
      content_text: "Primeira resposta direta",
      author: { username: "filho1" },
      likes_count: 0,
      replies_count: 0,
    },
  ];

  it("1. Renderiza cabeçalho de conversa, ancestrais, comentário focado HERO e respostas", () => {
    renderThread({
      post: mockPost,
      ancestors: mockAncestors,
      focusedComment: mockFocusedComment,
      replies: mockReplies,
    });

    expect(screen.getByText("Conversa")).toBeInTheDocument();
    expect(screen.getByText("Comentário raiz ancestral")).toBeInTheDocument();
    expect(screen.getByText("Comentário pai intermediário")).toBeInTheDocument();
    expect(screen.getByText("Comentário focado em destaque HERO")).toBeInTheDocument();
    expect(screen.getByText("Primeira resposta direta")).toBeInTheDocument();
    expect(window.HTMLElement.prototype.scrollIntoView).toHaveBeenCalled();
  });

  it("2. Botão de sair do foco chama onExitFocus", () => {
    const onExitFocusMock = vi.fn();

    renderThread({
      post: mockPost,
      ancestors: mockAncestors,
      focusedComment: mockFocusedComment,
      replies: mockReplies,
      onExitFocus: onExitFocusMock,
    });

    const exitBtn = screen.getByTestId("exit-focus-btn");
    fireEvent.click(exitBtn);

    expect(onExitFocusMock).toHaveBeenCalled();
  });

  it("3. Botão de voltar ao anterior chama onBackToParent", () => {
    const onBackToParentMock = vi.fn();

    renderThread({
      post: mockPost,
      ancestors: mockAncestors,
      focusedComment: mockFocusedComment,
      replies: mockReplies,
      onBackToParent: onBackToParentMock,
    });

    const backBtn = screen.getByTestId("back-to-parent-btn");
    fireEvent.click(backBtn);

    expect(onBackToParentMock).toHaveBeenCalled();
  });

  it("4. Carrega mais respostas ao clicar no botão de paginação", async () => {
    vi.spyOn(apiModule, "getCommentReplies").mockResolvedValueOnce({
      items: [
        {
          id: "reply-2",
          content_text: "Segunda resposta carregada via cursor",
          author: { username: "filho2" },
          likes_count: 0,
          replies_count: 0,
        },
      ],
      next_cursor: null,
    });

    renderThread({
      post: mockPost,
      ancestors: mockAncestors,
      focusedComment: mockFocusedComment,
      replies: mockReplies,
      nextCursor: "cursor_token_123",
    });

    const loadMoreBtn = screen.getByTestId("load-more-replies-btn");
    fireEvent.click(loadMoreBtn);

    await waitFor(() => {
      expect(apiModule.getCommentReplies).toHaveBeenCalledWith("focused-1", "recent", "cursor_token_123");
      expect(screen.getByText("Segunda resposta carregada via cursor")).toBeInTheDocument();
    });
  });

  it("5. Exibe mensagem de vazio quando não há respostas diretas", () => {
    renderThread({
      post: mockPost,
      ancestors: [],
      focusedComment: mockFocusedComment,
      replies: [],
    });

    expect(
      screen.getByText("Nenhuma resposta ainda. Seja o primeiro a responder!")
    ).toBeInTheDocument();
  });

  it("6. Submete resposta local ao comentário focado e atualiza lista", async () => {
    const onReplySubmitMock = vi.fn().mockResolvedValue({
      id: "reply-new",
      content_text: "Resposta criada na thread focada",
      author: { username: "novo_autor" },
      likes_count: 0,
      replies_count: 0,
    });

    renderThread({
      post: mockPost,
      ancestors: [],
      focusedComment: mockFocusedComment,
      replies: [],
      onReplySubmit: onReplySubmitMock,
    });

    const replyBtn = screen.getByTestId("reply-btn-focused-1");
    fireEvent.click(replyBtn);

    const replyInput = screen.getByTestId("reply-input-focused-1");
    fireEvent.change(replyInput, { target: { value: "Resposta criada na thread focada" } });

    const submitBtn = screen.getByTestId("reply-submit-btn-focused-1");
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(onReplySubmitMock).toHaveBeenCalledWith("Resposta criada na thread focada", "focused-1");
      expect(screen.getByText("Resposta criada na thread focada")).toBeInTheDocument();
    });
  });

  it("7. Exclusão de resposta direta remove o item da lista", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.spyOn(apiModule, "deleteComment").mockResolvedValueOnce({});
    const onDeleteMock = vi.fn();

    renderThread({
      post: mockPost,
      ancestors: [],
      focusedComment: mockFocusedComment,
      replies: [
        {
          id: "reply-to-del",
          content_text: "Resposta a ser apagada",
          author: { username: "autor_del" },
          can_delete: true,
        },
      ],
      onDeleteComment: onDeleteMock,
    });

    expect(screen.getByText("Resposta a ser apagada")).toBeInTheDocument();

    const delBtn = screen.getByTestId("delete-comment-btn-reply-to-del");
    fireEvent.click(delBtn);

    await waitFor(() => {
      expect(onDeleteMock).toHaveBeenCalledWith("reply-to-del");
      expect(screen.queryByText("Resposta a ser apagada")).not.toBeInTheDocument();
    });
  });

  it("8. Exclusão do comentário focado HERO chama onDeleteComment", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.spyOn(apiModule, "deleteComment").mockResolvedValueOnce({});
    const onDeleteMock = vi.fn();

    renderThread({
      post: mockPost,
      ancestors: [],
      focusedComment: mockFocusedComment,
      replies: [],
      onDeleteComment: onDeleteMock,
    });

    const delHeroBtn = screen.getByTestId("delete-comment-btn-focused-1");
    fireEvent.click(delHeroBtn);

    await waitFor(() => {
      expect(onDeleteMock).toHaveBeenCalledWith("focused-1");
    });
  });
});
