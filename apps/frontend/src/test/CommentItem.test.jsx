import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import CommentItem from "../components/CommentItem";
import * as apiModule from "../services/api";
import "../i18n";

function renderComment(props) {
  return render(
    <MemoryRouter>
      <CommentItem {...props} />
    </MemoryRouter>
  );
}

describe("CommentItem Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const getBaseComment = () => ({
    id: "comment-1",
    content_text: "Olá @mariana tudo bem?",
    author: { username: "carlos", avatar: null },
    created_at: new Date().toISOString(),
    likes_count: 5,
    replies_count: 2,
    is_liked: false,
    is_bookmarked: false,
    can_edit: true,
    can_delete: true,
    is_deleted: false,
    is_placeholder: false,
    preview_replies: [],
  });

  it("1. Renderiza autor, menção segura com link e contadores", () => {
    renderComment({ comment: getBaseComment(), postId: "post-1" });

    expect(screen.getByText("carlos")).toBeInTheDocument();
    expect(screen.getByText("@mariana")).toBeInTheDocument();
    expect(screen.getByText("@mariana").closest("a")).toHaveAttribute("href", "/profile/mariana");
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("2. Curtir comentário chama toggleCommentLike e atualiza contagem", async () => {
    vi.spyOn(apiModule, "toggleCommentLike").mockResolvedValueOnce({
      is_liked: true,
      likes_count: 6,
    });

    renderComment({ comment: getBaseComment(), postId: "post-1" });

    const likeBtn = screen.getByTestId("like-btn-comment-1");
    fireEvent.click(likeBtn);

    await waitFor(() => {
      expect(apiModule.toggleCommentLike).toHaveBeenCalledWith("comment-1");
      expect(screen.getByText("6")).toBeInTheDocument();
    });
  });

  it("3. Salvar comentário chama toggleCommentBookmark e altera estado", async () => {
    vi.spyOn(apiModule, "toggleCommentBookmark").mockResolvedValueOnce({
      is_bookmarked: true,
    });

    renderComment({ comment: getBaseComment(), postId: "post-1" });

    const bookmarkBtn = screen.getByTestId("bookmark-btn-comment-1");
    fireEvent.click(bookmarkBtn);

    await waitFor(() => {
      expect(apiModule.toggleCommentBookmark).toHaveBeenCalledWith("comment-1");
    });
  });

  it("4. Edição de comentário permite alterar texto e salvar", async () => {
    vi.spyOn(apiModule, "editComment").mockResolvedValueOnce({
      id: "comment-1",
      content_text: "Texto alterado com sucesso",
      is_edited: true,
    });

    renderComment({ comment: getBaseComment(), postId: "post-1" });

    const editBtn = screen.getByTestId("edit-comment-btn-comment-1");
    fireEvent.click(editBtn);

    const textarea = screen.getByDisplayValue("Olá @mariana tudo bem?");
    fireEvent.change(textarea, { target: { value: "Texto alterado com sucesso" } });

    const saveBtn = screen.getByTestId("save-edit-btn");
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(apiModule.editComment).toHaveBeenCalledWith("comment-1", "Texto alterado com sucesso");
    });
  });

  it("5. Exclusão de comentário pede confirmação e chama onDelete", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.spyOn(apiModule, "deleteComment").mockResolvedValueOnce({});
    const onDeleteMock = vi.fn();

    renderComment({
      comment: getBaseComment(),
      postId: "post-1",
      onDelete: onDeleteMock,
    });

    const deleteBtn = screen.getByTestId("delete-comment-btn-comment-1");
    fireEvent.click(deleteBtn);

    await waitFor(() => {
      expect(apiModule.deleteComment).toHaveBeenCalledWith("comment-1");
      expect(onDeleteMock).toHaveBeenCalledWith("comment-1");
    });
  });

  it("6. Renderiza tombstone quando is_deleted=true sem vazar autor", () => {
    const tombstoneComment = {
      ...getBaseComment(),
      is_deleted: true,
      author: null,
      content_text: "[comment deleted]",
      can_edit: false,
      can_delete: false,
    };

    const { rerender } = renderComment({ comment: tombstoneComment, postId: "post-1" });

    expect(screen.getByTestId("tombstone-text")).toHaveTextContent("[comentário excluído]");
    expect(screen.queryByText("carlos")).not.toBeInTheDocument();
    expect(screen.getByText("[removido]")).toBeInTheDocument();

    // Renderiza tombstone em modo Hero
    rerender(
      <MemoryRouter>
        <CommentItem comment={tombstoneComment} postId="post-1" hero={true} />
      </MemoryRouter>
    );
    expect(screen.getByTestId("tombstone-text")).toHaveTextContent("[comentário excluído]");
    expect(screen.getByText("[removido]")).toBeInTheDocument();
  });

  it("7. Renderiza placeholder quando nó ancestral está indisponível", () => {
    const placeholderComment = {
      ...getBaseComment(),
      is_placeholder: true,
      author: null,
      content_text: "[indisponível]",
    };

    const { rerender } = renderComment({ comment: placeholderComment, postId: "post-1" });

    expect(screen.getAllByText("[indisponível]").length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByText("carlos")).not.toBeInTheDocument();

    rerender(
      <MemoryRouter>
        <CommentItem comment={placeholderComment} postId="post-1" hero={true} />
      </MemoryRouter>
    );
    expect(screen.getAllByText("[indisponível]").length).toBeGreaterThanOrEqual(1);
  });

  it("8. Resposta inline abre compositor, submete e chama onReplySubmit", async () => {
    const onReplySubmitMock = vi.fn().mockResolvedValue({ id: "reply-1" });
    const setActiveReplyIdMock = vi.fn();

    renderComment({
      comment: getBaseComment(),
      postId: "post-1",
      activeReplyId: "comment-1",
      setActiveReplyId: setActiveReplyIdMock,
      onReplySubmit: onReplySubmitMock,
    });

    const replyInput = screen.getByTestId("reply-input-comment-1");
    fireEvent.change(replyInput, { target: { value: "Minha resposta" } });

    const replySubmit = screen.getByTestId("reply-submit-btn-comment-1");
    fireEvent.click(replySubmit);

    await waitFor(() => {
      expect(onReplySubmitMock).toHaveBeenCalledWith("Minha resposta", "comment-1");
    });
  });

  it("9. Focar conversa ao clicar em comentário com profundidade >= 2", () => {
    const onFocusThreadMock = vi.fn();
    const deepComment = {
      ...getBaseComment(),
      depth: 2,
    };

    renderComment({
      comment: deepComment,
      postId: "post-1",
      depth: 2,
      onFocusThread: onFocusThreadMock,
    });

    const focusBtn = screen.getByTestId("focus-btn-comment-1");
    fireEvent.click(focusBtn);

    expect(onFocusThreadMock).toHaveBeenCalledWith(deepComment);

    // Clica diretamente no artigo/card para disparar handleCardClick
    const article = screen.getByRole("article");
    fireEvent.click(article);
    expect(onFocusThreadMock).toHaveBeenCalledTimes(2);
  });

  it("10. Cancelar edição e cancelar resposta fecham os respectivos formulários", () => {
    const setActiveReplyIdMock = vi.fn();

    const { rerender } = renderComment({
      comment: getBaseComment(),
      postId: "post-1",
      activeReplyId: "comment-1",
      setActiveReplyId: setActiveReplyIdMock,
    });

    // Cancela resposta
    const cancelReplyBtn = screen.getByText("Cancelar");
    fireEvent.click(cancelReplyBtn);
    expect(setActiveReplyIdMock).toHaveBeenCalledWith(null);

    // Rerender sem resposta ativa
    rerender(
      <MemoryRouter>
        <CommentItem comment={getBaseComment()} postId="post-1" />
      </MemoryRouter>
    );

    // Abre edição e cancela
    const editBtn = screen.getByTestId("edit-comment-btn-comment-1");
    fireEvent.click(editBtn);
    expect(screen.getByDisplayValue("Olá @mariana tudo bem?")).toBeInTheDocument();

    const cancelEditBtn = screen.getByText("Cancelar");
    fireEvent.click(cancelEditBtn);
    expect(screen.queryByDisplayValue("Olá @mariana tudo bem?")).not.toBeInTheDocument();
  });

  it("11. Renderiza respostas aninhadas inline até depth 2", () => {
    const parentComment = {
      ...getBaseComment(),
      preview_replies: [
        {
          id: "child-1",
          content_text: "Resposta filha",
          author: { username: "filho_user", avatar: "http://example.com/avatar.jpg" },
          likes_count: 0,
          replies_count: 0,
          can_edit: false,
          can_delete: false,
          preview_replies: [],
        },
      ],
    };

    renderComment({
      comment: parentComment,
      postId: "post-1",
      depth: 0,
    });

    expect(screen.getByText("Resposta filha")).toBeInTheDocument();
    expect(screen.getByText("filho_user")).toBeInTheDocument();
  });

  it("12. Modo HERO: renderiza avatar, edição e resposta no Hero", async () => {
    vi.spyOn(apiModule, "editComment").mockResolvedValueOnce({
      id: "comment-1",
      content_text: "Texto editado no hero",
      is_edited: true,
    });
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.spyOn(apiModule, "deleteComment").mockResolvedValueOnce({});
    const onDeleteMock = vi.fn();

    const heroComment = {
      ...getBaseComment(),
      author: { username: "carlos", avatar: "http://example.com/carlos.jpg" },
      is_edited: true,
    };

    renderComment({
      comment: heroComment,
      postId: "post-1",
      hero: true,
      connectFromAbove: true,
      activeReplyId: "comment-1",
      onDelete: onDeleteMock,
    });

    expect(screen.getByText(/editado/)).toBeInTheDocument();

    // Testa edição no hero
    const editBtn = screen.getByTestId("edit-comment-btn-comment-1");
    fireEvent.click(editBtn);
    const textarea = screen.getByDisplayValue("Olá @mariana tudo bem?");
    fireEvent.change(textarea, { target: { value: "Texto editado no hero" } });
    const saveBtn = screen.getByTestId("save-edit-btn");
    fireEvent.click(saveBtn);
    await waitFor(() => {
      expect(apiModule.editComment).toHaveBeenCalled();
    });

    // Testa exclusão no hero
    const deleteBtn = screen.getByTestId("delete-comment-btn-comment-1");
    fireEvent.click(deleteBtn);
    await waitFor(() => {
      expect(onDeleteMock).toHaveBeenCalledWith("comment-1");
    });
  });

  it("13. Dono do post oculta e reexibe comentário de terceiro", async () => {
    vi.spyOn(apiModule, "hideComment").mockResolvedValueOnce({});
    vi.spyOn(apiModule, "unhideComment").mockResolvedValueOnce({});

    const thirdPartyComment = {
      ...getBaseComment(),
      can_edit: false,
      can_delete: false,
      can_hide: true,
      is_hidden: false,
    };

    renderComment({
      comment: thirdPartyComment,
      postId: "post-1",
      currentUserId: "post-owner-id",
    });

    // Ocultar
    const hideBtn = screen.getByTestId("hide-comment-btn-comment-1");
    fireEvent.click(hideBtn);

    await waitFor(() => {
      expect(apiModule.hideComment).toHaveBeenCalledWith("comment-1");
    });
  });

  it("14. Terceiro abre menu «…» do comentário e silencia/bloqueia autor com confirmação", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.spyOn(apiModule, "muteUser").mockResolvedValueOnce({});
    vi.spyOn(apiModule, "blockUser").mockResolvedValueOnce({});
    const onDeleteMock = vi.fn();

    const otherUserComment = {
      ...getBaseComment(),
      can_edit: false,
      can_delete: false,
      can_hide: false,
    };

    renderComment({
      comment: otherUserComment,
      postId: "post-1",
      currentUserId: "different-user-id",
      onDelete: onDeleteMock,
    });

    const muteBtn = screen.getByTestId("mute-comment-user-btn-comment-1");
    fireEvent.click(muteBtn);
    await waitFor(() => {
      expect(apiModule.muteUser).toHaveBeenCalledWith("carlos");
    });

    const blockBtn = screen.getByTestId("block-comment-user-btn-comment-1");
    fireEvent.click(blockBtn);
    await waitFor(() => {
      expect(apiModule.blockUser).toHaveBeenCalledWith("carlos");
      expect(onDeleteMock).toHaveBeenCalledWith("comment-1");
    });
  });

  it("15. Abre e fecha menu de ações do comentário ao clicar no backdrop", () => {
    renderComment({ comment: getBaseComment(), postId: "post-1" });
    const menuBtn = screen.getByTestId("comment-menu-btn-comment-1");
    fireEvent.click(menuBtn);
    const backdrop = document.querySelector(".fixed.inset-0");
    expect(backdrop).toBeInTheDocument();
    fireEvent.click(backdrop);
    expect(document.querySelector(".fixed.inset-0")).not.toBeInTheDocument();
  });

  it("16. Cancela confirmação de silenciar e bloquear no comentário", () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    const muteSpy = vi.spyOn(apiModule, "muteUser");
    const blockSpy = vi.spyOn(apiModule, "blockUser");

    renderComment({
      comment: { ...getBaseComment(), can_edit: false, can_delete: false, can_hide: false },
      postId: "post-1",
      currentUserId: "different-user-id",
    });

    fireEvent.click(screen.getByTestId("mute-comment-user-btn-comment-1"));
    fireEvent.click(screen.getByTestId("block-comment-user-btn-comment-1"));

    expect(muteSpy).not.toHaveBeenCalled();
    expect(blockSpy).not.toHaveBeenCalled();
  });

  it("17. Renderiza placeholder de conta bloqueada em modo normal e modo hero", () => {
    const blockedComment = {
      ...getBaseComment(),
      id: "blocked-1",
      author: null,
      content_text: "",
      is_placeholder: true,
      placeholder_reason: "block",
    };

    const { unmount } = renderComment({ comment: blockedComment, postId: "post-1" });
    expect(screen.getByTestId("blocked-comment-text")).toHaveTextContent(
      "[comentário de conta bloqueada]"
    );
    expect(screen.getByText("[conta bloqueada]")).toBeInTheDocument();
    unmount();

    // Modo Hero
    renderComment({ comment: blockedComment, postId: "post-1", hero: true });
    expect(screen.getByTestId("blocked-comment-text")).toHaveTextContent(
      "[comentário de conta bloqueada]"
    );
  });

  it("18. Colapsa comentário de usuário silenciado com botão de mostrar/ocultar", () => {
    const mutedComment = {
      ...getBaseComment(),
      id: "muted-1",
      content_text: "Texto do usuário silenciado",
      is_muted: true,
    };

    renderComment({ comment: mutedComment, postId: "post-1" });
    const showBtn = screen.getByTestId("show-muted-comment-muted-1");
    expect(showBtn).toHaveTextContent("Mostrar comentário");
    expect(screen.queryByText("Texto do usuário silenciado")).not.toBeInTheDocument();

    // Expande
    fireEvent.click(showBtn);
    expect(screen.getByText("Texto do usuário silenciado")).toBeInTheDocument();
    expect(screen.getByText("Ocultar")).toBeInTheDocument();

    // Oculta novamente
    fireEvent.click(screen.getByText("Ocultar"));
    expect(screen.getByTestId("show-muted-comment-muted-1")).toBeInTheDocument();
  });
});
