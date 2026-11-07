import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { PostCard } from "../components/PostCard";
import { api } from "../services/api";
import "../i18n";

function renderCard(post) {
  return render(
    <MemoryRouter>
      <PostCard post={post} />
    </MemoryRouter>
  );
}

describe("PostCard Component — Curtidas e Salvos", () => {
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
  };

  it("1. Renderiza conteúdo, autor e contadores iniciais", () => {
    renderCard(basePost);

    expect(screen.getByTestId("post-content")).toHaveTextContent("Conteúdo para teste de interação");
    expect(screen.getByText("@alice")).toBeInTheDocument();
    expect(screen.getByTestId("likes-count")).toHaveTextContent("5");
    expect(screen.getByTestId("bookmarks-count")).toHaveTextContent("2");
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
    expect(likeBtn).toHaveTextContent("♥");

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith("/api/posts/post-123/like/");
    });

    // Descurtir (DELETE)
    fireEvent.click(likeBtn);
    expect(likesCount).toHaveTextContent("5");
    expect(likeBtn).toHaveTextContent("♡");

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
      expect(likeBtn).toHaveTextContent("♡");
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
    expect(bookmarkBtn).toHaveTextContent("🔖");

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith("/api/posts/post-123/bookmark/");
    });

    // Remover dos salvos
    fireEvent.click(bookmarkBtn);
    expect(bookmarksCount).toHaveTextContent("2");
    expect(bookmarkBtn).toHaveTextContent("🏷");

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
});

