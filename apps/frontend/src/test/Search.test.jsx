import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Search } from "../pages/Search";
import { api } from "../services/api";
import "../i18n";

describe("Search Page Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("1. Renderiza input de busca e alterna entre abas Pessoas e Posts", () => {
    render(
      <MemoryRouter>
        <Search />
      </MemoryRouter>
    );

    expect(screen.getByTestId("search-input")).toBeInTheDocument();
    const tabPeople = screen.getByTestId("tab-people");
    const tabPosts = screen.getByTestId("tab-posts");

    expect(tabPeople).toBeInTheDocument();
    expect(tabPosts).toBeInTheDocument();

    fireEvent.click(tabPosts);
    expect(tabPosts).toHaveClass("border-white");
  });

  it("2. Realiza busca de pessoas com avatar e conta privada, e trata resultado vazio", async () => {
    vi.spyOn(api, "get")
      .mockResolvedValueOnce({
        data: {
          results: [
            { username: "usuario1", avatar: null, is_private: false },
            { username: "usuario2", avatar: "http://example.com/avatar.jpg", is_private: true },
          ],
        },
      })
      .mockResolvedValueOnce({
        data: { results: [] },
      });

    render(
      <MemoryRouter>
        <Search />
      </MemoryRouter>
    );

    const input = screen.getByTestId("search-input");
    const submitBtn = screen.getByTestId("search-submit");

    fireEvent.change(input, { target: { value: "usuario" } });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText("@usuario1")).toBeInTheDocument();
      expect(screen.getByText("@usuario2")).toBeInTheDocument();
      expect(screen.getByText("🔒")).toBeInTheDocument();
    });

    // Busca sem resultados
    fireEvent.change(input, { target: { value: "nao_existe" } });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByTestId("empty-search-people")).toBeInTheDocument();
    });
  });

  it("3. Realiza busca de posts e trata resultado vazio", async () => {
    vi.spyOn(api, "get")
      .mockResolvedValueOnce({
        data: [
          {
            id: "post-search-1",
            author: { username: "autor_post" },
            content_text: "Conteúdo encontrado na busca",
            created_at: new Date().toISOString(),
          },
        ],
      })
      .mockResolvedValueOnce({
        data: [],
      });

    render(
      <MemoryRouter initialEntries={["/search?tab=posts"]}>
        <Search />
      </MemoryRouter>
    );

    const input = screen.getByTestId("search-input");
    const submitBtn = screen.getByTestId("search-submit");

    fireEvent.change(input, { target: { value: "conteudo" } });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText("Conteúdo encontrado na busca")).toBeInTheDocument();
    });

    // Busca vazia de posts
    fireEvent.change(input, { target: { value: "zero_posts" } });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByTestId("empty-search-posts")).toBeInTheDocument();
    });
  });

  it("4. Trata erro na requisição de busca e limpa quando q < 2", async () => {
    vi.spyOn(api, "get").mockRejectedValueOnce(new Error("Erro na busca"));

    render(
      <MemoryRouter>
        <Search />
      </MemoryRouter>
    );

    const input = screen.getByTestId("search-input");
    const submitBtn = screen.getByTestId("search-submit");

    fireEvent.change(input, { target: { value: "erro" } });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByTestId("search-error")).toBeInTheDocument();
    });

    // Query com 1 caractere não faz busca e exibe aviso
    fireEvent.change(input, { target: { value: "a" } });
    fireEvent.click(submitBtn);

    expect(screen.getByText("Digite pelo menos 2 caracteres para buscar.")).toBeInTheDocument();
  });
});
