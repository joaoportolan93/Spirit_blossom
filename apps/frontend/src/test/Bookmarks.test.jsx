import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Bookmarks } from "../pages/Bookmarks";
import { api } from "../services/api";
import * as apiModule from "../services/api";
import "../i18n";

function renderBookmarks() {
  return render(
    <MemoryRouter>
      <Bookmarks />
    </MemoryRouter>
  );
}

describe("Bookmarks Page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("1. Exibe estado de carregamento e depois lista os posts salvos", async () => {
    const mockSavedPosts = [
      {
        id: "saved-1",
        content_text: "Post guardado para ler depois",
        created_at: new Date().toISOString(),
        author: { username: "carlos" },
        is_bookmarked: true,
        bookmarks_count: 1,
      },
    ];

    vi.spyOn(api, "get").mockResolvedValueOnce({ data: mockSavedPosts });

    renderBookmarks();

    expect(screen.getByTestId("bookmarks-loading")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("Post guardado para ler depois")).toBeInTheDocument();
      expect(screen.getByText("@carlos")).toBeInTheDocument();
      expect(screen.getByTestId("bookmarks-posts-list")).toBeInTheDocument();
    });
  });

  it("2. Exibe mensagem de vazio quando não há itens salvos", async () => {
    vi.spyOn(api, "get").mockResolvedValueOnce({ data: [] });

    renderBookmarks();

    await waitFor(() => {
      expect(screen.getByTestId("empty-bookmarks")).toBeInTheDocument();
      expect(screen.getByText("Nenhuma publicação salva ainda.")).toBeInTheDocument();
    });
  });

  it("3. Trata erro na requisição sem quebrar a tela", async () => {
    vi.spyOn(api, "get").mockRejectedValueOnce(new Error("Network error"));

    renderBookmarks();

    await waitFor(() => {
      expect(screen.getByTestId("empty-bookmarks")).toBeInTheDocument();
    });
  });

  it("4. Alterna para aba de comentários salvos e lista itens", async () => {
    vi.spyOn(api, "get").mockResolvedValueOnce({ data: [] });
    vi.spyOn(apiModule, "getBookmarkedComments").mockResolvedValueOnce({
      items: [
        {
          id: "comment-bm-1",
          content_text: "Comentário importante salvo",
          author: { username: "ana", avatar: null },
          likes_count: 3,
          replies_count: 0,
          is_liked: false,
          is_bookmarked: true,
        },
      ],
      next_cursor: null,
    });

    renderBookmarks();

    const commentsTab = screen.getByTestId("tab-comments");
    fireEvent.click(commentsTab);

    await waitFor(() => {
      expect(screen.getByTestId("bookmarks-comments-list")).toBeInTheDocument();
      expect(screen.getByText("Comentário importante salvo")).toBeInTheDocument();
    });
  });

  it("5. Exibe mensagem vazia na aba de comentários", async () => {
    vi.spyOn(api, "get").mockResolvedValueOnce({ data: [] });
    vi.spyOn(apiModule, "getBookmarkedComments").mockResolvedValueOnce({
      items: [],
      next_cursor: null,
    });

    renderBookmarks();

    const commentsTab = screen.getByTestId("tab-comments");
    fireEvent.click(commentsTab);

    await waitFor(() => {
      expect(screen.getByTestId("empty-comments-bookmarks")).toBeInTheDocument();
    });
  });
});

