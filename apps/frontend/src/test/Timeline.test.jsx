import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Feed } from "../pages/Feed";
import { api } from "../services/api";
import "../i18n";

function renderWithRouter(ui) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

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

    renderWithRouter(<Feed />);

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

    renderWithRouter(<Feed />);

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

    renderWithRouter(<Feed />);


    await waitFor(() => {
      expect(screen.getByTestId("load-more-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("load-more-btn"));

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith("/api/posts/?cursor=post-uuid-19");
      expect(screen.getByText("Post da página 2")).toBeInTheDocument();
    });
  });

  it("4. Alterna para a aba 'Para você' e carrega feed de exploração", async () => {
    vi.spyOn(api, "get")
      .mockResolvedValueOnce({ data: [] }) // following
      .mockResolvedValueOnce({
        data: [
          {
            id: "foryou-1",
            content_text: "Post recomendado",
            created_at: new Date().toISOString(),
            author: { username: "diana" },
          },
        ],
      }); // for_you

    renderWithRouter(<Feed />);

    await waitFor(() => {
      expect(screen.getByTestId("feed-empty")).toBeInTheDocument();
    });

    const forYouTab = screen.getByRole("tab", { name: "Para você" });
    fireEvent.click(forYouTab);

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith("/api/feed/explore/");
      expect(screen.getByText("Post recomendado")).toBeInTheDocument();
      expect(screen.getByText("@diana")).toBeInTheDocument();
    });
  });

  it("5. Abre modal do compositor ao clicar no botão '+ Novo Post'", async () => {
    vi.spyOn(api, "get").mockResolvedValueOnce({ data: [] });

    renderWithRouter(<Feed />);

    const newPostBtn = screen.getByTestId("feed-new-post-btn");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    fireEvent.click(newPostBtn);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("6. Cria post pelo modal do Feed e insere no topo da timeline", async () => {
    vi.spyOn(api, "get").mockResolvedValueOnce({ data: [] });
    vi.spyOn(api, "post").mockResolvedValueOnce({
      data: {
        id: "post-created-1",
        content_text: "Post novinho criado via modal!",
        created_at: new Date().toISOString(),
        author: { username: "me" },
      },
    });

    renderWithRouter(<Feed />);

    await waitFor(() => {
      expect(screen.getByTestId("feed-empty")).toBeInTheDocument();
    });

    // Abre modal
    fireEvent.click(screen.getByTestId("feed-new-post-btn"));
    const textarea = screen.getByTestId("composer-textarea");
    fireEvent.change(textarea, { target: { value: "Post novinho criado via modal!" } });

    // Publica
    fireEvent.click(screen.getByTestId("publish-button"));

    await waitFor(() => {
      expect(screen.getByText("Post novinho criado via modal!")).toBeInTheDocument();
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });

  it("7. Exibe estado vazio na aba 'Para você' quando não há recomendações", async () => {
    vi.spyOn(api, "get")
      .mockResolvedValueOnce({ data: [] }) // following
      .mockResolvedValueOnce({ data: [] }); // for_you

    renderWithRouter(<Feed />);

    await waitFor(() => {
      expect(screen.getByTestId("feed-empty")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("tab", { name: "Para você" }));

    await waitFor(() => {
      expect(
        screen.getByText("Nenhuma recomendação para você no momento.")
      ).toBeInTheDocument();
    });
  });
});
