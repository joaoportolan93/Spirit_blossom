import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Bookmarks } from "../pages/Bookmarks";
import { api } from "../services/api";
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
});

