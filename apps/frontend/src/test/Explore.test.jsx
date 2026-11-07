import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Explore } from "../pages/Explore";
import { api } from "../services/api";
import "../i18n";

describe("Explore Page Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("1. Carrega feed explorar e busca os detalhes dos posts e pagina com load-more", async () => {
    vi.spyOn(api, "get").mockImplementation((url) => {
      if (url === "/api/feed/explore/") {
        return Promise.resolve({
          data: {
            items: [
              { post_id: "p1", reason: "explore", cursor: "p1" },
              { post_id: "p_invalido", reason: "explore", cursor: "p_invalido" },
            ],
            next_cursor: "p1",
          },
        });
      }
      if (url === "/api/feed/explore/?cursor=p1") {
        return Promise.resolve({
          data: {
            items: [{ post_id: "p2", reason: "explore", cursor: "p2" }],
            next_cursor: null,
          },
        });
      }
      if (url === "/api/posts/p1/") {
        return Promise.resolve({
          data: {
            id: "p1",
            author: { username: "explorador" },
            content_text: "Post descoberto no Explorar!",
            created_at: new Date().toISOString(),
          },
        });
      }
      if (url === "/api/posts/p2/") {
        return Promise.resolve({
          data: {
            id: "p2",
            author: { username: "outro_explorador" },
            content_text: "Segundo post carregado!",
            created_at: new Date().toISOString(),
          },
        });
      }
      // Simula 404 para p_invalido
      return Promise.reject(new Error("Post não encontrado"));
    });

    render(
      <MemoryRouter>
        <Explore />
      </MemoryRouter>
    );

    expect(screen.getByTestId("explore-loading")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("Post descoberto no Explorar!")).toBeInTheDocument();
      expect(screen.getByText("@explorador")).toBeInTheDocument();
      expect(screen.getByTestId("explore-load-more")).toBeInTheDocument();
    });

    // Clica em carregar mais
    fireEvent.click(screen.getByTestId("explore-load-more"));

    await waitFor(() => {
      expect(screen.getByText("Segundo post carregado!")).toBeInTheDocument();
      expect(screen.queryByTestId("explore-load-more")).not.toBeInTheDocument();
    });
  });

  it("2. Exibe estado vazio quando não há posts no feed explorar", async () => {
    vi.spyOn(api, "get").mockResolvedValueOnce({
      data: { items: [], next_cursor: null },
    });

    render(
      <MemoryRouter>
        <Explore />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId("empty-explore")).toBeInTheDocument();
    });
  });

  it("3. Lida com erro no carregamento do feed explorar", async () => {
    vi.spyOn(api, "get").mockRejectedValueOnce(new Error("Network Error"));

    render(
      <MemoryRouter>
        <Explore />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId("empty-explore")).toBeInTheDocument();
    });
  });
});
