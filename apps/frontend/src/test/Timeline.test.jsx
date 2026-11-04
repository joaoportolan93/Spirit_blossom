import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { Feed } from "../pages/Feed";
import { api } from "../services/api";
import "../i18n";

describe("Timeline Component (3 testes)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("1. Renderiza lista de publicações carregadas da API", async () => {
    const mockPosts = [
      {
        id: "post-1",
        content_text: "Primeiro post no feed",
        created_at: new Date().toISOString(),
        author: { username: "alice" },
      },
      {
        id: "post-2",
        content_text: "Segundo post no feed",
        created_at: new Date().toISOString(),
        author: { username: "bob" },
      },
    ];

    vi.spyOn(api, "get").mockResolvedValueOnce({ data: mockPosts });

    render(<Feed />);

    expect(screen.getByTestId("feed-loading")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("Primeiro post no feed")).toBeInTheDocument();
      expect(screen.getByText("Segundo post no feed")).toBeInTheDocument();
      expect(screen.getByText("@alice")).toBeInTheDocument();
      expect(screen.getByText("@bob")).toBeInTheDocument();
    });
  });

  it("2. Exibe mensagem de estado vazio quando não há publicações", async () => {
    vi.spyOn(api, "get").mockResolvedValueOnce({ data: [] });

    render(<Feed />);

    await waitFor(() => {
      expect(screen.getByTestId("feed-empty")).toBeInTheDocument();
      expect(
        screen.getByText("Nenhuma publicação ainda. Siga alguém para ver atualizações!")
      ).toBeInTheDocument();
    });
  });

  it("3. Renderiza botão de 'Carregar mais' e aciona paginação", async () => {
    // 20 posts retornados simulando página cheia
    const mock20Posts = Array.from({ length: 20 }, (_, i) => ({
      id: `post-uuid-${i}`,
      content_text: `Post número ${i}`,
      created_at: new Date().toISOString(),
      author: { username: `user_${i}` },
    }));

    vi.spyOn(api, "get")
      .mockResolvedValueOnce({ data: mock20Posts })
      .mockResolvedValueOnce({
        data: [
          {
            id: "post-uuid-21",
            content_text: "Post da página 2",
            created_at: new Date().toISOString(),
            author: { username: "charlie" },
          },
        ],
      });

    render(<Feed />);

    await waitFor(() => {
      expect(screen.getByTestId("load-more-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("load-more-btn"));

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith("/api/posts/?cursor=post-uuid-19");
      expect(screen.getByText("Post da página 2")).toBeInTheDocument();
    });
  });
});
